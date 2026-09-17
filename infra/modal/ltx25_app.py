"""LTX-2.5 (22B distilled, 8-step) with its Gemma 4 12B text encoder, on Modal.

Challenger to infra/modal/ltx2_app.py (LTX-2.3). A separate app with its own
name, so deploying it never touches the live LTX-2.3 endpoint.

Same request/response contract as ltx2_app.py, so scripts/modal_client.py can
call either:
    POST {prompt, width, height, num_frames, fps, seed, image_base64?}
    ->   {success, video_base64, seed, width, height, num_frames, fps, inference_time_ms}

negative_prompt is accepted and ignored: the distilled model runs at CFG 1.

Licence: LTX-2.x Community License (2026-08-11) — free below $10M annual
revenue; Attachment A use restrictions and the AI-transparency clause (§6)
apply. Gemma 4 ships inside Lightricks' text-encoder file.

Deploy (from the repo root):   modal deploy infra/modal/ltx25_app.py
Endpoint env var:              MODAL_LTX25_ENDPOINT_URL  (infra/modal/.env)
"""

import modal

app = modal.App("kyros-ltx25")

HF_REPO = "Lightricks/LTX-2.5"
# Pinned: a rebuild downloads exactly these weights. Bump deliberately.
HF_REVISION = "5e6e71018ee1756ed329b697a7b4aedc934dfce9"  # main @ 2026-09-01
LTX2_COMMIT = "a95ab856bf29407b6b066ede0abe1846050db56c"   # LTX-2 main @ 2026-08-25 (LTX-2.5 + Gemma 4)
MODEL_DIR = "/models/ltx25"
FILES = {
    "transformer": "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
    "text_encoder": "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
    "video_vae": "vae/ltx-2.5-video-vae-bf16.safetensors",
    "audio_vae": "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "duration_head": "model_patches/ltx-2.5-duration-head-bf16.safetensors",
    "spatial_upsampler": "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
}

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    # LTX-2 main calls torch>=2.8 APIs; its CUDA 13.2 wheels are only for the
    # optional natten kernel, so a CUDA 12.8 build keeps us on Modal's drivers.
    .pip_install(
        "torch==2.9.1", "torchaudio==2.9.1", "torchvision==0.24.1",
        index_url="https://download.pytorch.org/whl/cu128",
    )
    # ltx-core bounds transformers to >=5.8,<5.15 (5.15 breaks the Gemma 4 encoder).
    .pip_install("transformers==5.14.1", "huggingface_hub>=0.34", "fastapi[standard]")
    .run_commands(
        f"git clone https://github.com/Lightricks/LTX-2.git /app/ltx2 && cd /app/ltx2 && git checkout {LTX2_COMMIT}",
        "pip install -e /app/ltx2/packages/ltx-core -e /app/ltx2/packages/ltx-pipelines",
    )
    .run_commands(
        "python -c \""
        "from huggingface_hub import snapshot_download; "
        f"snapshot_download('{HF_REPO}', revision='{HF_REVISION}', local_dir='{MODEL_DIR}', "
        f"allow_patterns={list(FILES.values())!r})"
        "\"",
        secrets=[modal.Secret.from_name("huggingface-secret")],
    )
)


@app.cls(
    image=image.env({"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}),
    gpu="A100-80GB",
    timeout=900,
    scaledown_window=60,
)
@modal.concurrent(max_inputs=1)
class LTX25:
    @modal.enter()
    def load(self):
        import os
        import time

        from ltx_pipelines.distilled import DistilledPipeline
        from ltx_pipelines.utils.model_paths import ModelPaths

        p = {k: os.path.join(MODEL_DIR, v) for k, v in FILES.items()}
        t0 = time.time()
        self.pipeline = DistilledPipeline(
            model_paths=ModelPaths.from_split(
                transformer_path=p["transformer"],
                text_encoder_path=p["text_encoder"],
                video_vae_path=p["video_vae"],
                audio_vae_path=p["audio_vae"],
                duration_head_path=p["duration_head"],
            ),
            spatial_upsampler_path=p["spatial_upsampler"],
            loras=(),
        )
        print(f"LTX-2.5 distilled loaded in {time.time() - t0:.1f}s")

    @modal.fastapi_endpoint(method="POST")
    def generate(self, request: dict) -> dict:
        import base64
        import io
        import os
        import random
        import shutil
        import tempfile
        import time

        import torch
        from PIL import Image

        prompt = request.get("prompt")
        if not prompt:
            return {"error": "Missing required 'prompt' field"}
        width = (int(request.get("width", 576)) // 32) * 32
        height = (int(request.get("height", 1024)) // 32) * 32
        num_frames = int(request.get("num_frames", 121))
        if (num_frames - 1) % 8 != 0:
            num_frames = ((num_frames - 1 + 4) // 8) * 8 + 1
        fps = int(request.get("fps", 24))
        seed = request.get("seed")
        seed = random.randint(0, 2**32 - 1) if seed is None else int(seed)

        work = tempfile.mkdtemp(prefix="ltx25_")
        try:
            from ltx_core.model.video_vae import AUTO_TILING, get_video_chunks_number
            from ltx_pipelines.utils.args import ImageConditioningInput
            from ltx_pipelines.utils.media_io import encode_video

            images = []
            b64 = request.get("image_base64")
            if b64:
                if "," in b64:
                    b64 = b64.split(",", 1)[1]
                img_path = os.path.join(work, "input.png")
                Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB").save(img_path)
                images = [ImageConditioningInput(path=img_path, frame_idx=0, strength=1.0)]

            out_path = os.path.join(work, "output.mp4")
            t0 = time.time()
            with torch.inference_mode():
                result = self.pipeline(
                    prompt=prompt, seed=seed, height=height, width=width,
                    frame_rate=float(fps), images=images, num_frames=num_frames,
                    tiling_config=AUTO_TILING,
                )
                encode_video(
                    video=result.video, fps=fps, audio=result.audio, output_path=out_path,
                    video_chunks_number=get_video_chunks_number(result.num_frames, result.tiling_config),
                )
            with open(out_path, "rb") as f:
                video_b64 = base64.b64encode(f.read()).decode("utf-8")
            return {"success": True, "video_base64": video_b64, "seed": seed,
                    "width": width, "height": height, "num_frames": result.num_frames,
                    "fps": fps, "inference_time_ms": int((time.time() - t0) * 1000)}
        except torch.cuda.OutOfMemoryError as e:
            torch.cuda.empty_cache()
            return {"error": f"GPU out of memory: {e}"}
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {"error": f"Internal error: {e}"}
        finally:
            shutil.rmtree(work, ignore_errors=True)
