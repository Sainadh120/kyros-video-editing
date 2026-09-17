"""Qwen-Image-2512 text-to-image on Modal — challenger to infra/modal/flux2_app.py.

A separate app, so deploying it never touches the live FLUX.2 endpoint.

Same request/response contract as flux2_app.py (text-to-image only):
    POST {prompt, width, height, seed, negative_prompt?, num_inference_steps?, guidance_scale?}
    ->   {success, image_base64, seed, image_size, inference_time_ms, native_size}

The model is trained around 1.6 MP, so it renders at its own resolution for the
requested aspect (928x1664, 1664x928, 1328x1328, ...) and is resized down to
the requested size — the fair comparison with FLUX.2 at our production sizes.

Licence: Apache 2.0. Not gated.

Deploy (from the repo root):   modal deploy infra/modal/qwen_image_app.py
Endpoint env var:              MODAL_QWEN_IMAGE_ENDPOINT_URL  (infra/modal/.env)
"""

import modal

app = modal.App("kyros-qwen-image")

MODEL_ID = "Qwen/Qwen-Image-2512"
# Pinned: a rebuild downloads exactly these weights. Bump deliberately.
MODEL_REVISION = "25468b98e3276ca6700de15c6628e51b7de54a26"  # main @ 2025-12-31
MODEL_DIR = "/models/qwen-image"
# The model card's recommended sizes per aspect ratio.
NATIVE = {"1:1": (1328, 1328), "16:9": (1664, 928), "9:16": (928, 1664),
          "4:3": (1472, 1104), "3:4": (1104, 1472), "3:2": (1584, 1056), "2:3": (1056, 1584)}
# The model card's default negative prompt (in Chinese: low resolution, low
# quality, deformed limbs and fingers, oversaturated, waxy, faces without
# detail, over-smooth, AI look, messy composition, blurry/distorted text).
DEFAULT_NEGATIVE = "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch==2.9.1", "torchvision==0.24.1",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    .pip_install("diffusers==0.40.0", "transformers==5.14.1", "accelerate>=1.0",
                 "safetensors", "sentencepiece", "Pillow", "huggingface_hub>=1.23,<2",
                 "fastapi[standard]")
    .run_commands(
        "python -c \""
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download('{MODEL_ID}', revision='{MODEL_REVISION}', local_dir='{MODEL_DIR}')"
        "\""
    )
)


@app.cls(image=image, gpu="A100-80GB", timeout=900, scaledown_window=60)
@modal.concurrent(max_inputs=1)
class QwenImage:
    @modal.enter()
    def load(self):
        import time

        import torch
        from diffusers import DiffusionPipeline

        t0 = time.time()
        self.pipe = DiffusionPipeline.from_pretrained(MODEL_DIR, torch_dtype=torch.bfloat16).to("cuda")
        print(f"Qwen-Image-2512 loaded in {time.time() - t0:.1f}s")

    @modal.fastapi_endpoint(method="POST")
    def generate(self, request: dict) -> dict:
        import base64
        import io
        import random
        import time

        import torch
        from PIL import Image

        prompt = request.get("prompt")
        if not prompt:
            return {"error": "Missing required 'prompt' field"}
        width = int(request.get("width", 1024))
        height = int(request.get("height", 1024))
        seed = request.get("seed")
        seed = random.randint(0, 2**32 - 1) if seed is None else int(seed)
        ratio = width / height
        nw, nh = min(NATIVE.values(), key=lambda wh: abs(wh[0] / wh[1] - ratio))
        t0 = time.time()
        try:
            with torch.inference_mode():
                out = self.pipe(
                    prompt=prompt,
                    negative_prompt=request.get("negative_prompt") or DEFAULT_NEGATIVE,
                    width=nw, height=nh,
                    num_inference_steps=int(request.get("num_inference_steps") or 50),
                    true_cfg_scale=float(request.get("guidance_scale") or 4.0),
                    generator=torch.Generator(device="cuda").manual_seed(seed),
                )
            img = out.images[0]
            # Crop to the exact requested aspect, then resize down.
            target = width / height
            iw, ih = img.size
            if iw / ih > target:
                cw = int(round(ih * target))
                img = img.crop(((iw - cw) // 2, 0, (iw - cw) // 2 + cw, ih))
            else:
                ch = int(round(iw / target))
                img = img.crop((0, (ih - ch) // 2, iw, (ih - ch) // 2 + ch))
            img = img.resize((width, height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return {"success": True, "image_base64": base64.b64encode(buf.getvalue()).decode("utf-8"),
                    "seed": seed, "image_size": [width, height], "native_size": [nw, nh],
                    "inference_time_ms": int((time.time() - t0) * 1000)}
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            return {"error": f"GPU out of memory: {e}"}
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": f"Internal error: {e}"}
