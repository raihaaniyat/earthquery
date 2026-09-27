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


def load_pil_image(image_path: str, max_dim: int = 2048) -> Image.Image:
    is_tiff = image_path.lower().endswith((".tif", ".tiff"))
    if is_tiff:
        try:
            import rasterio
            from rasterio.enums import Resampling
            import numpy as np
            with rasterio.open(image_path) as src:
                count = src.count
                w, h = src.width, src.height
                scale = min(1.0, max_dim / max(w, h))
                out_w = max(int(w * scale), 64)
                out_h = max(int(h * scale), 64)

                if count >= 3:
                    arr = src.read([1, 2, 3], out_shape=(3, out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
                    rgb = arr.transpose(1, 2, 0)
                elif count == 2:
                    b1 = src.read(1, out_shape=(out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
                    b2 = src.read(2, out_shape=(out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
                    chosen = b2 if np.std(b2) > np.std(b1) else b1
                    rgb = np.repeat(chosen[:, :, np.newaxis], 3, axis=2)
                elif count == 1:
                    b1 = src.read(1, out_shape=(out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
                    rgb = np.repeat(b1[:, :, np.newaxis], 3, axis=2)
                else:
                    arr = src.read(out_shape=(count, out_h, out_w), resampling=Resampling.bilinear).astype(np.float32)
                    rgb = np.repeat(arr[0, :, :, np.newaxis], 3, axis=2)

                p2, p98 = np.percentile(rgb, (2, 98))
                if p98 > p2:
                    rgb_scaled = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                else:
                    max_v = float(rgb.max())
                    if max_v > 0:
                        rgb_scaled = np.clip(rgb / max_v * 255.0, 0, 255).astype(np.uint8)
                    else:
                        rgb_scaled = np.zeros_like(rgb, dtype=np.uint8)
                return Image.fromarray(rgb_scaled)
        except Exception:
            pass

    try:
        im = Image.open(image_path)
        if max(im.size) > max_dim:
            scale = max_dim / max(im.size)
            im = im.resize((max(int(im.size[0] * scale), 64), max(int(im.size[1] * scale), 64)), Image.Resampling.BILINEAR)
        if im.mode == "LA":
            l, a = im.split()
            import numpy as np
            l_arr = np.array(l)
            if np.std(l_arr) == 0 and np.std(np.array(a)) > 0:
                return a.convert("RGB")
            return l.convert("RGB")
        return im.convert("RGB")
    except Exception:
        return Image.new("RGB", (448, 448), color=(0, 0, 0))


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
        max_tokens = min(int(req.parameters.get("max_tokens", 1536)), 2048)

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

        context = req.parameters.get("context", "")
        context_block = f"\n\nSpecialist Instrument & Model Observations:\n{context}\n" if context else ""

        scientific_instructions = (
            "You are SatQuery AI, an expert remote sensing satellite imagery analyst. "
            "Analyze the satellite imagery thoroughly and provide an in-depth, structured scientific response.\n\n"
            f"User Question: {prompt}\n"
            f"{context_block}\n"
            "Requirements for your analysis:\n"
            "1. Treat the user's question as your primary objective and directly answer every part of it immediately.\n"
            "2. Identify the image / scene type (e.g. high-resolution optical, multispectral satellite, urban, rural, coastal, or blank/unexposed).\n"
            "3. Detail all observable physical geography, terrain features, vegetation, water bodies, and anthropogenic structures (buildings, roads, vehicles, etc.). If the image is blank or lacks contrast, state this honestly and do not invent objects.\n"
            "4. Describe spatial and location patterns (e.g. upper-left quadrant, central region, lower-right corridor).\n"
            "5. Clearly distinguish observed visual facts from analytical interpretations.\n"
            "6. State confidence levels (high, moderate, uncertain) and scientific limitations.\n"
            "7. Organize your response with the following markdown headings:\n"
            "## Direct Answer\n"
            "## Image / Scene Type\n"
            "## What Is Present in the Image\n"
            "## Detailed Visual Analysis\n"
            "## Spatial / Location Information\n"
            "## Confidence\n"
            "## Limitations\n"
            "## Conclusion"
        )
        question = f"<image>\n{scientific_instructions}"

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
