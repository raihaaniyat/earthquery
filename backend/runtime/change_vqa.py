"""
Paired-Image Change VQA Subprocess Entry Point.
Runs within `satquery-core` (Python 3.11, PyTorch 2.10, CUDA 13).
Performs bitemporal natural language change reasoning using Siamese VLM Cross-Attention model.
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
torch.backends.cudnn.enabled = False  # Blackwell CC 12.0 stability

from torchvision import transforms
from PIL import Image
from transformers import AutoTokenizer

from backend.models.change_vqa import ChangeVQAModel, CHANGE_CATEGORIES, CHANGE_MAGNITUDES
from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION


def main():
    parser = argparse.ArgumentParser(description="Paired Change VQA Subprocess Runner")
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
        ckpt_path = REPO_ROOT / "models" / "ChangeVQA" / "change_vqa_best.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Change VQA trained weights not found at: {ckpt_path}")

        t1_path = req.asset_references.get("image_t1") or req.asset_references.get("t1") or req.asset_references.get("image")
        t2_path = req.asset_references.get("image_t2") or req.asset_references.get("t2") or t1_path

        if not t1_path or not os.path.exists(t1_path):
            raise FileNotFoundError(f"Pre-event image asset not found: {t1_path}")
        if not t2_path or not os.path.exists(t2_path):
            raise FileNotFoundError(f"Post-event image asset not found: {t2_path}")

        prompt = req.parameters.get("prompt") or req.parameters.get("query") or "What changed between these two acquisition dates?"

        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
        model = ChangeVQAModel(vocab_size=tokenizer.vocab_size, embed_dim=512, num_heads=8)

        ckpt = torch.load(str(ckpt_path), map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        model.to(device)
        model.eval()

        # Image transforms
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        img_t1 = Image.open(t1_path).convert("RGB")
        img_t2 = Image.open(t2_path).convert("RGB")

        t1_tensor = transform(img_t1).unsqueeze(0).to(device)
        t2_tensor = transform(img_t2).unsqueeze(0).to(device)

        encoded = tokenizer(
            prompt,
            padding="max_length",
            truncation=True,
            max_length=32,
            return_tensors="pt"
        )
        input_ids = encoded["input_ids"].to(device)

        # Generate natural language reasoning answer
        result = model.generate_answer(t1_tensor, t2_tensor, input_ids, prompt)

        peak_vram = None
        if torch.cuda.is_available():
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_metadata={
                "model": "Paired-Image Change VQA (Siamese VLM Cross-Attention)",
                "task": "change_vqa",
                "question": prompt,
                "answer": result["answer"],
                "text": result["answer"],
                "summary": result["answer"],
                "change_detected": result["change_detected"],
                "change_category": result["change_category"],
                "change_magnitude": result["change_magnitude"],
                "confidence": result["confidence"],
                "probabilities": result["probabilities"],
                "temporal_direction": "T1 (Pre-event) -> T2 (Post-event)",
                "vram_allocated_mb": round(peak_vram, 2) if peak_vram else 0.0,
                "note": "Trained on CDVQA benchmark for bitemporal satellite change reasoning."
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
            error_code="CHANGE_VQA_INFERENCE_ERROR",
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
