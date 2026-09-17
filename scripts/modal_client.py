#!/usr/bin/env python3
"""The one place Kyros talks to its own model servers on Modal.

    infra/modal/flux2_app.py  ->  MODAL_FLUX2_ENDPOINT_URL
    infra/modal/ltx2_app.py   ->  MODAL_LTX2_ENDPOINT_URL

Each server is a synchronous Modal web endpoint: one JSON POST, the result
comes back in the response (base64, or a presigned URL when the server was
given R2 credentials). Modal answers a long call with a 303 to its result;
urllib follows it. Standard library only — no toolkit, no uv project.

Endpoint URLs come from the environment first, then infra/modal/.env
(gitignored — the URLs are account-specific).
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "infra" / "modal" / ".env"


def read_env_file(p=None):
    env = {}
    p = Path(p or ENV_FILE)
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def endpoint(key):
    return os.environ.get(key) or read_env_file().get(key)


def payload_for(tool, req, input_path=None):
    """The JSON body each server's `generate` reads (see infra/modal/*_app.py)."""
    if tool in ("flux2", "qwen_image"):
        body = {"prompt": req["prompt"], "width": req["width"], "height": req["height"],
                "seed": req["seed"]}
        if req.get("steps"):
            body["num_inference_steps"] = req["steps"]
        if req.get("guidance"):
            body["guidance_scale"] = req["guidance"]
        if req.get("negative"):
            body["negative_prompt"] = req["negative"]
        if input_path:
            body["operation"] = "edit"
            body["image_base64"] = _b64(input_path)
        return body
    if tool in ("ltx2", "ltx25"):
        body = {"prompt": req["prompt"], "width": req["width"], "height": req["height"],
                "num_frames": req["numFrames"], "fps": req["fps"], "seed": req["seed"],
                "quality": req.get("quality", "standard"),
                "negative_prompt": req["negative"]}
        if req.get("steps"):
            body["num_inference_steps"] = req["steps"]
        if input_path:
            body["image_base64"] = _b64(input_path)
        return body
    if tool == "image_edit":
        body = {"prompt": req["prompt"], "seed": req["seed"], "image_base64": _b64(input_path)}
        if req.get("negative"):
            body["negative_prompt"] = req["negative"]
        return body
    raise ValueError(f"unknown tool {tool!r}")


def _b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def post(url, body, timeout):
    """POST JSON, return (result dict, elapsed seconds). Never raises."""
    data = json.dumps(body).encode()
    rq = urllib.request.Request(url, data=data, method="POST",
                                headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        hint = {408: "Modal function timed out", 503: "Modal is scaling up or unavailable",
                422: "Modal rejected the request"}.get(e.code, f"HTTP {e.code}")
        return {"error": f"{hint}: {detail}"}, time.time() - t0
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}, time.time() - t0
    try:
        return json.loads(text), time.time() - t0
    except ValueError:
        return {"error": f"non-JSON response: {text[:200]}"}, time.time() - t0


def save_result(result, out_path, timeout=300):
    """Write the returned media to out_path. Returns an error string or None."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if result.get("error"):
        return result["error"]
    b64 = result.get("image_base64") or result.get("video_base64")
    if b64:
        out.write_bytes(base64.b64decode(b64))
        return None
    if result.get("output_url"):
        try:
            with urllib.request.urlopen(result["output_url"], timeout=timeout) as r:
                out.write_bytes(r.read())
            return None
        except Exception as e:
            return f"download failed: {e}"
    return "the server returned no media"


def generate(tool, req, out_path, env_key, timeout, input_path=None):
    """One request end to end. Returns {"ok", "elapsedSec", "error", "server"}."""
    url = endpoint(env_key)
    if not url:
        return {"ok": False, "elapsedSec": 0.0, "error": f"{env_key} is not set"}
    result, elapsed = post(url, payload_for(tool, req, input_path), timeout)
    err = save_result(result, out_path)
    ok = err is None and Path(out_path).exists() and Path(out_path).stat().st_size > 0
    meta = {k: result.get(k) for k in ("seed", "inference_time_ms", "image_size",
                                         "num_frames", "fps") if k in result}
    return {"ok": ok, "elapsedSec": elapsed, "error": None if ok else (err or "empty output"),
            "server": meta}
