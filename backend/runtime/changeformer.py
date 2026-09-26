"""
ChangeFormerV6 Subprocess Entry Point.
Runs within `satquery-changeformer` (Python 3.9, Torch 2.6).
Performs bitemporal optical change detection on Pre-event (T1) and Post-event (T2) images.
Reconstructs full-resolution 2D binary change masks (0=unchanged, 1=changed).
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

changeformer_repo = str(REPO_ROOT / "models" / "ChangeFormer_repo")
if changeformer_repo not in sys.path:
    sys.path.insert(0, changeformer_repo)

import torch
import numpy as np
from PIL import Image

try:
    from models.ChangeFormer import ChangeFormerV6
    HAS_CHANGEFORMER = True
except ImportError:
    HAS_CHANGEFORMER = False

from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION


def load_tensor_image(img_path: str, target_size=(256, 256)) -> torch.Tensor:
    """Loads image and normalizes to (1, 3, H, W) tensor in [0, 1]."""
    img = Image.open(img_path).convert("RGB")
    if target_size:
        img = img.resize(target_size, Image.Resampling.BILINEAR)
    arr = np.array(img).astype(np.float32) / 255.0
    arr = np.transpose(arr, (2, 0, 1))  # (3, H, W)
    return torch.from_numpy(arr).unsqueeze(0).float()


def main():
    parser = argparse.ArgumentParser(description="ChangeFormerV6 Subprocess Runner")
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
        if not HAS_CHANGEFORMER:
            raise ImportError("ChangeFormerV6 class could not be imported from models/ChangeFormer_repo.")

        ckpt_path = str(
            REPO_ROOT / "models" / "ChangeFormer" /
            "CD_ChangeFormerV6_LEVIR_b16_lr0.0001_adamw_train_test_200_linear_ce_multi_train_True_multi_infer_False_shuffle_AB_False_embed_dim_256" /
            "best_ckpt.pt"
        )
        if not os.path.exists(ckpt_path):
            raise FileNotFoundError(f"ChangeFormer checkpoint not found at: {ckpt_path}")

        # Execute on CPU initially per Phase 1/Phase 7 specs
        device = "cpu"

        model = ChangeFormerV6(input_nc=3, output_nc=2, embed_dim=256)
        checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
        state_dict = checkpoint["model_G_state_dict"] if "model_G_state_dict" in checkpoint else checkpoint

        clean_state_dict = {}
        for k, v in state_dict.items():
            name = k[7:] if k.startswith("module.") else k
            clean_state_dict[name] = v

        model.load_state_dict(clean_state_dict, strict=True)
        model.to(device).eval()

        t1_path = req.asset_references.get("image_t1") or req.asset_references.get("asset_a")
        t2_path = req.asset_references.get("image_t2") or req.asset_references.get("asset_b")

        if not t1_path or not os.path.exists(t1_path):
            raise FileNotFoundError(f"Pre-event image asset not found: {t1_path}")
        if not t2_path or not os.path.exists(t2_path):
            raise FileNotFoundError(f"Post-event image asset not found: {t2_path}")

        orig_img_1 = Image.open(t1_path)
        orig_w, orig_h = orig_img_1.size

        t1_tensor = load_tensor_image(t1_path, target_size=(256, 256)).to(device)
        t2_tensor = load_tensor_image(t2_path, target_size=(256, 256)).to(device)

        with torch.no_grad():
            logits = model(t1_tensor, t2_tensor)
            if isinstance(logits, (list, tuple)):
                logits = logits[0]
            prob = torch.softmax(logits, dim=1)
            pred_mask = torch.argmax(prob, dim=1).squeeze().cpu().numpy().astype(np.uint8)

        # Scale prediction back to original dimensions if needed
        mask_pil = Image.fromarray(pred_mask * 255)
        if (orig_w, orig_h) != (256, 256):
            mask_pil = mask_pil.resize((orig_w, orig_h), Image.Resampling.NEAREST)

        mask_out_path = str(out_dir / "change_mask.png")
        mask_pil.save(mask_out_path)

        mask_np = np.array(mask_pil) > 0
        total_pixels = int(mask_np.size)
        changed_pixels = int(np.sum(mask_np))
        change_ratio = float(changed_pixels / total_pixels) if total_pixels > 0 else 0.0

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_assets={"change_mask": mask_out_path},
            output_metadata={
                "model": "ChangeFormerV6",
                "checkpoint": "LEVIR-CD",
                "total_pixels": total_pixels,
                "changed_pixels": changed_pixels,
                "change_percentage": round(change_ratio * 100.0, 2),
                "resolution": [orig_w, orig_h],
                "mask_classes": {"0": "unchanged", "1": "changed"}
            },
            metrics=SubprocessMetrics(
                duration_ms=(time.time() - t_start) * 1000.0,
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
            error_code="CHANGEFORMER_INFERENCE_ERROR",
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
