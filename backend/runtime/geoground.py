"""
OWLv2 GeoGround Subprocess Entry Point.
Runs within `satquery-core` (Python 3.11, PyTorch 2.10, CUDA 13).
Replaces the oversized GeoGround-7B (13.16 GB) with google/owlv2-base-patch16-ensemble.
Executes open-vocabulary zero-shot visual grounding and object localization well within 6 GB VRAM limit (~590 MiB).
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

from PIL import Image, ImageDraw
from transformers import Owlv2Processor, Owlv2ForObjectDetection

from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION


def parse_prompts(raw_prompt: str) -> list:
    if not raw_prompt or not raw_prompt.strip():
        return ["building", "vegetation", "water", "vehicle", "structure"]
    
    text = raw_prompt.strip()
    for prefix in ["locate", "detect", "find", "identify", "ground"]:
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            if text.lower().startswith("all"):
                text = text[3:].strip()
            if text.lower().startswith("the"):
                text = text[3:].strip()

    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if parts:
            return parts
    if " and " in text.lower():
        parts = [p.strip() for p in text.lower().split(" and ") if p.strip()]
        if parts:
            return parts

    return [text]


def load_pil_image(image_path: str) -> Image.Image:
    try:
        return Image.open(image_path).convert("RGB")
    except Exception:
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


def main():
    parser = argparse.ArgumentParser(description="OWLv2 GeoGround Subprocess Runner")
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
        input_image = req.asset_references.get("image") or req.asset_references.get("original")
        if not input_image or not os.path.exists(input_image):
            raise FileNotFoundError(f"Input image asset not found: {input_image}")

        prompt = req.parameters.get("prompt") or req.parameters.get("query") or ""
        queries = parse_prompts(prompt)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = "google/owlv2-base-patch16-ensemble"

        processor = Owlv2Processor.from_pretrained(model_name)
        model = Owlv2ForObjectDetection.from_pretrained(model_name).to(device).eval()

        image = load_pil_image(input_image)
        texts = [queries]

        inputs = processor(text=texts, images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)

        target_sizes = torch.Tensor([image.size[::-1]]).to(device)
        results = processor.post_process_object_detection(
            outputs=outputs,
            target_sizes=target_sizes,
            threshold=float(req.parameters.get("threshold", 0.1))
        )

        boxes = results[0]["boxes"].tolist()
        scores = results[0]["scores"].tolist()
        labels = results[0]["labels"].tolist()

        detections = []
        for i in range(len(boxes)):
            lbl_idx = labels[i]
            lbl_text = queries[lbl_idx] if lbl_idx < len(queries) else f"label_{lbl_idx}"
            box = [round(v, 1) for v in boxes[i]]
            score = round(float(scores[i]), 4)
            detections.append({
                "label": lbl_text,
                "score": score,
                "box": box
            })

        detections.sort(key=lambda d: d["score"], reverse=True)

        # Generate visual overlay image with bounding boxes
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated)
        for det in detections:
            box = det["box"]
            draw.rectangle(box, outline="#FF3333", width=2)
            draw.text((box[0] + 3, max(0, box[1] - 12)), f"{det['label']} {det['score']:.2f}", fill="#FF3333")
        
        overlay_path = str(out_dir / "grounding_overlay.png")
        annotated.save(overlay_path)

        label_counts = {}
        for d in detections:
            label_counts[d["label"]] = label_counts.get(d["label"], 0) + 1
        count_summary = ", ".join(f"{cnt} {lbl}" for lbl, cnt in label_counts.items())

        summary_text = (
            f"Visual grounding completed with OWLv2: detected {len(detections)} object regions "
            f"matching queries [{', '.join(queries)}]. Breakdown: {count_summary if count_summary else 'No objects detected at confidence threshold.'}."
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
            output_assets={"grounding_overlay": overlay_path},
            output_metadata={
                "model": "OWLv2 GeoGround (google/owlv2-base-patch16-ensemble)",
                "queries": queries,
                "total_detections": len(detections),
                "detections": detections[:50],
                "summary": summary_text,
                "text": summary_text,
                "vram_allocated_mb": round(peak_vram, 2) if peak_vram else 0.0,
                "note": "Open-vocabulary zero-shot visual grounding replacing GeoGround-7B. Operates within 6 GB VRAM limit (~590 MiB allocated)."
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
            error_code="GEOGROUND_INFERENCE_ERROR",
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

