"""
UPerNet ConvNeXt-Tiny Subprocess Entry Point.
Runs within `satquery-core` (Python 3.11, PyTorch 2.10, CUDA 13).
Generates land-cover semantic segmentation masks (ADE20K demo mapping).
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
torch.backends.cudnn.enabled = False

import numpy as np
from PIL import Image
from transformers import AutoImageProcessor, UperNetForSemanticSegmentation

from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION


def main():
    parser = argparse.ArgumentParser(description="UPerNet Subprocess Runner")
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
        model_dir = str(REPO_ROOT / "models" / "upernet-convnext-tiny")
        if not os.path.exists(model_dir):
            raise FileNotFoundError(f"UPerNet checkpoint not found at: {model_dir}")

        input_image = req.asset_references.get("image") or req.asset_references.get("original")
        if not input_image or not os.path.exists(input_image):
            raise FileNotFoundError(f"Input image asset not found: {input_image}")

        device = "cuda" if torch.cuda.is_available() else "cpu"

        processor = AutoImageProcessor.from_pretrained(model_dir)
        model = UperNetForSemanticSegmentation.from_pretrained(model_dir).to(device).eval()

        def load_pil_image(image_path: str) -> Image.Image:
            try:
                return Image.open(image_path).convert("RGB")
            except Exception:
                try:
                    import rasterio
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

        image = load_pil_image(input_image)
        orig_w, orig_h = image.size

        inputs = processor(images=image, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits

        upsampled_logits = torch.nn.functional.interpolate(
            logits,
            size=(orig_h, orig_w),
            mode="bilinear",
            align_corners=False
        )
        pred_seg = upsampled_logits.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)

        # Save class segmentation mask
        mask_out_path = str(out_dir / "segmentation_mask.png")
        Image.fromarray(pred_seg).save(mask_out_path)

        # Identify present classes
        unique_classes, counts = np.unique(pred_seg, return_counts=True)
        total_pixels = int(pred_seg.size)
        detected_classes = []
        for cls_id, cnt in zip(unique_classes, counts):
            cls_name = model.config.id2label.get(int(cls_id), f"class_{cls_id}")
            fraction = round(float(cnt / total_pixels) * 100.0, 2)
            detected_classes.append({"class_id": int(cls_id), "name": cls_name, "percentage": fraction})

        # Sort by largest presence
        detected_classes.sort(key=lambda x: x["percentage"], reverse=True)

        peak_vram = None
        if torch.cuda.is_available():
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_assets={"segmentation_mask": mask_out_path},
            output_metadata={
                "model": "UPerNet ConvNeXt-Tiny",
                "label_map": "ADE20K Scene Parsing",
                "detected_classes": detected_classes[:10],
                "note": "Pretrained ADE20K classes represent demo proxy. Satellite land cover requires domain-specific head."
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
            error_code="UPERNET_INFERENCE_ERROR",
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
