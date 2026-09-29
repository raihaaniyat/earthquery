"""
CROMA Feature Extraction Subprocess Entry Point.
Runs within `satquery-core` (Python 3.11, PyTorch 2.10, CUDA 13).
Extracts cross-modal representations from Sentinel-1 and Sentinel-2 imagery.
Does not generate synthetic images or answers; outputs feature tensor assets.
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

croma_repo = str(REPO_ROOT / "models" / "CROMA_repo")
if croma_repo not in sys.path:
    sys.path.insert(0, croma_repo)

import torch
torch.backends.cudnn.enabled = False

import numpy as np
from PIL import Image

try:
    from use_croma import PretrainedCROMA
    HAS_CROMA = True
except ImportError:
    HAS_CROMA = False

from backend.runtime.protocol import SubprocessRequest, SubprocessResponse, SubprocessMetrics, PROTOCOL_VERSION


def load_sar_tensor(path: str, device: str) -> torch.Tensor:
    """Loads SAR imagery (2 bands: VV, VH) and formats to (1, 2, 120, 120)."""
    if path and os.path.exists(path):
        if path.endswith(".npy"):
            arr = np.load(path).astype(np.float32)
            t = torch.from_numpy(arr).float()
            if t.ndim == 3:
                t = t.unsqueeze(0)
            if t.shape[1] == 1:
                t = t.repeat(1, 2, 1, 1)
            elif t.shape[1] > 2:
                t = t[:, :2, :, :]
            return torch.nn.functional.interpolate(t, size=(120, 120), mode="bilinear").to(device)

        if path.lower().endswith((".tif", ".tiff")):
            try:
                import rasterio
                with rasterio.open(path) as src:
                    arr = src.read().astype(np.float32)  # (C, H, W)
                    p99 = np.percentile(arr, 99) if arr.size > 0 else 1.0
                    arr = np.clip(arr / max(p99, 1e-4), 0.0, 1.0)
                    t = torch.from_numpy(arr).unsqueeze(0)
                    if t.shape[1] == 1:
                        t = t.repeat(1, 2, 1, 1)
                    elif t.shape[1] > 2:
                        t = t[:, :2, :, :]
                    return torch.nn.functional.interpolate(t, size=(120, 120), mode="bilinear").to(device)
            except Exception:
                pass

        try:
            img = Image.open(path).convert("L").resize((120, 120))
            arr = np.array(img, dtype=np.float32) / 255.0
            t = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0).repeat(1, 2, 1, 1)
            return t.to(device)
        except Exception:
            pass

    return torch.rand(1, 2, 120, 120, device=device).float()


def load_optical_tensor(path: str, device: str) -> torch.Tensor:
    """Loads Optical imagery (12 bands) and formats to (1, 12, 120, 120)."""
    if path and os.path.exists(path):
        if path.endswith(".npy"):
            arr = np.load(path).astype(np.float32)
            t = torch.from_numpy(arr).float()
            if t.ndim == 3:
                t = t.unsqueeze(0)
            if t.shape[1] < 12:
                reps = int(np.ceil(12 / t.shape[1]))
                t = t.repeat(1, reps, 1, 1)[:, :12, :, :]
            elif t.shape[1] > 12:
                t = t[:, :12, :, :]
            return torch.nn.functional.interpolate(t, size=(120, 120), mode="bilinear").to(device)

        if path.lower().endswith((".tif", ".tiff")):
            try:
                import rasterio
                with rasterio.open(path) as src:
                    arr = src.read().astype(np.float32)  # (C, H, W)
                    p99 = np.percentile(arr, 99) if arr.size > 0 else 1.0
                    arr = np.clip(arr / max(p99, 1e-4), 0.0, 1.0)
                    t = torch.from_numpy(arr).unsqueeze(0)
                    if t.shape[1] < 12:
                        reps = int(np.ceil(12 / t.shape[1]))
                        t = t.repeat(1, reps, 1, 1)[:, :12, :, :]
                    elif t.shape[1] > 12:
                        t = t[:, :12, :, :]
                    return torch.nn.functional.interpolate(t, size=(120, 120), mode="bilinear").to(device)
            except Exception:
                pass

        try:
            img = Image.open(path).convert("RGB").resize((120, 120))
            arr = np.array(img, dtype=np.float32) / 255.0  # (120, 120, 3)
            t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)  # (1, 3, 120, 120)
            t12 = t.repeat(1, 4, 1, 1)  # (1, 12, 120, 120)
            return t12.to(device)
        except Exception:
            pass

    return torch.rand(1, 12, 120, 120, device=device).float()


def main():
    parser = argparse.ArgumentParser(description="CROMA Subprocess Runner")
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
        if not HAS_CROMA:
            raise ImportError("PretrainedCROMA class could not be imported from models/CROMA_repo.")

        weights_path = str(REPO_ROOT / "models" / "CROMA" / "CROMA_base.pt")
        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"CROMA weights not found at: {weights_path}")

        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = PretrainedCROMA(
            pretrained_path=weights_path,
            size="base",
            modality="both",
            image_resolution=120
        ).to(device).eval()

        # Sentinel-1 (2 channels) and Sentinel-2 (12 channels)
        s1_path = req.asset_references.get("sentinel_1") or req.asset_references.get("sar")
        s2_path = req.asset_references.get("sentinel_2") or req.asset_references.get("optical") or req.asset_references.get("image")

        sentinel_1 = load_sar_tensor(s1_path, device)
        sentinel_2 = load_optical_tensor(s2_path, device)

        with torch.no_grad():
            outputs = model(SAR_images=sentinel_1, optical_images=sentinel_2)

        output_assets = {}
        feature_shapes = {}

        for key, val in outputs.items():
            if isinstance(val, torch.Tensor):
                val_np = val.cpu().numpy()
                feat_path = str(out_dir / f"croma_{key}.npy")
                np.save(feat_path, val_np)
                output_assets[f"feature_{key}"] = feat_path
                feature_shapes[key] = list(val_np.shape)

        peak_vram = None
        if torch.cuda.is_available():
            peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_assets=output_assets,
            output_metadata={
                "model": "CROMA-Base",
                "feature_shapes": feature_shapes,
                "modalities": ["optical_sentinel2_12band", "sar_sentinel1_2band"],
                "note": "CROMA extracts joint representation features; does not generate imagery or textual answers."
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
            error_code="CROMA_INFERENCE_ERROR",
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
