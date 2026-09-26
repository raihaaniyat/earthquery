"""
InternVL3-2B Subprocess Entry Point.
Runs within `satquery-core` (Python 3.11, PyTorch 2.10, CUDA 13).
Adheres strictly to the SubprocessRequest / SubprocessResponse protocol.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Add project root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import torch
torch.backends.cudnn.enabled = False  # Windows Blackwell CC 12.0 stability

import torchvision.transforms as T
from torchvision.transforms.functional import InterpolationMode
from PIL import Image
from transformers import AutoModel, AutoTokenizer

from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transform(input_size=448):
    return T.Compose([
        T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def load_pil_image(image_path: str) -> Image.Image:
    try:
        return Image.open(image_path).convert("RGB")
    except Exception:
        # Fallback for 16-bit GeoTIFF / raw TIFF rasters
        try:
            import rasterio
            import numpy as np
            with rasterio.open(image_path) as src:
                data = src.read()
                if data.shape[0] >= 3:
                    rgb = data[:3].transpose(1, 2, 0).astype(np.float32)
                else:
                    rgb = np.repeat(data[0, :, :, np.newaxis], 3, axis=2).astype(np.float32)
                p2, p98 = np.percentile(rgb, (2, 98))
                if p98 > p2:
                    rgb = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                else:
                    rgb = (rgb / max(float(rgb.max()), 1.0) * 255.0).astype(np.uint8)
                return Image.fromarray(rgb)
        except Exception:
            import tifffile
            import numpy as np
            arr = tifffile.imread(image_path)
            if arr.ndim == 3 and arr.shape[2] >= 3:
                rgb = arr[:, :, :3].astype(np.float32)
            elif arr.ndim == 3 and arr.shape[0] >= 3:
                rgb = arr[:3, :, :].transpose(1, 2, 0).astype(np.float32)
            else:
                rgb = np.repeat(arr[:, :, np.newaxis], 3, axis=2).astype(np.float32)
            p2, p98 = np.percentile(rgb, (2, 98))
            if p98 > p2:
                rgb = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
            else:
                rgb = (rgb / max(float(rgb.max()), 1.0) * 255.0).astype(np.uint8)
            return Image.fromarray(rgb)


def load_single_image(image_path, input_size=448):
    image = load_pil_image(image_path)
    transform = build_transform(input_size)
    pixel_values = transform(image).unsqueeze(0)  # (1, 3, 448, 448) single tile
    return pixel_values


def main():
    parser = argparse.ArgumentParser(description="InternVL3-2B Subprocess Runner")
    parser.add_argument("--request-json", type=str, required=True)
    parser.add_argument("--response-json", type=str, required=True)
    args = parser.parse_args()

    t_start = time.time()

    with open(args.request_json, "r", encoding="utf-8") as f:
        req_data = json.load(f)
    req = SubprocessRequest(**req_data)

    out_dir = Path(req.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        model_dir = str(REPO_ROOT / "models" / "InternVL3-2B")
        input_image = req.asset_references.get("image") or req.asset_references.get("original")
        if not input_image or not os.path.exists(input_image):
            raise FileNotFoundError(f"Input image asset not found: {input_image}")

        prompt = req.parameters.get("prompt", "Describe this satellite scene in detail.")
        max_tokens = min(int(req.parameters.get("max_tokens", 128)), 512)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True, use_fast=False)
        model = AutoModel.from_pretrained(
            model_dir,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            use_flash_attn=False,
            trust_remote_code=True
        ).eval().to(device)

        pixel_values = load_single_image(input_image).to(dtype).to(device)
        question = f"<image>\n{prompt}"

        generation_config = dict(
            max_new_tokens=max_tokens,
            do_sample=False
        )

        with torch.no_grad():
            response_text = model.chat(
                tokenizer,
                pixel_values,
                question,
                generation_config
            )

        peak_vram = None
        if torch.cuda.is_available():
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_assets={},
            output_metadata={
                "answer": response_text,
                "prompt": prompt,
                "model": "InternVL3-2B",
                "max_tokens": max_tokens
            },
            metrics=SubprocessMetrics(
                duration_ms=(time.time() - t_start) * 1000.0,
                peak_vram_mb=peak_vram,
                device_name=device,
                cudnn_enabled=False
            )
        )
    except Exception as e:
        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=False,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            error_code="INTERNVL_INFERENCE_ERROR",
            error_message=str(e),
            metrics=SubprocessMetrics(
                duration_ms=(time.time() - t_start) * 1000.0,
                cudnn_enabled=False
            )
        )

    with open(args.response_json, "w", encoding="utf-8") as f:
        f.write(resp.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
