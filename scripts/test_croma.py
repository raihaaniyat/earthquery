import os
import sys
import torch
torch.backends.cudnn.enabled = False

# Add CROMA repo to path
croma_repo = os.path.abspath('models/CROMA_repo')
if croma_repo not in sys.path:
    sys.path.insert(0, croma_repo)

from use_croma import PretrainedCROMA

def run_croma_verification():
    weights_path = os.path.abspath('models/CROMA/CROMA_base.pt')
    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"CROMA weights not found at: {weights_path}")

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[CROMA] Initializing PretrainedCROMA on device: {device}...")
    print(f"[CROMA] Weights path: {weights_path} ({os.path.getsize(weights_path) / (1024*1024):.1f} MB)")

    # Instantiate model
    model = PretrainedCROMA(
        pretrained_path=weights_path,
        size='base',
        modality='both',
        image_resolution=120
    ).to(device).eval()

    print("[CROMA] Model successfully loaded.")

    # Create correctly shaped inputs:
    # Sentinel-1: 2 channels (VV, VH polarizations) at 120x120 resolution
    # Sentinel-2: 12 optical bands (excluding cirrus B10) at 120x120 resolution
    batch_size = 2
    sentinel_1 = torch.rand(batch_size, 2, 120, 120, device=device).float()
    sentinel_2 = torch.rand(batch_size, 12, 120, 120, device=device).float()

    print(f"[CROMA] Input Sentinel-1 (SAR 2-channel) shape: {sentinel_1.shape}")
    print(f"[CROMA] Input Sentinel-2 (Optical 12-channel) shape: {sentinel_2.shape}")
    print("[CROMA] NOTE: CROMA pretrained encoders strictly target Sentinel-1 (VV/VH) and Sentinel-2 (12 bands).")
    print("[CROMA] It DOES NOT directly support Indian satellites (Cartosat / RISAT) without cross-sensor calibration or fine-tuning.")

    with torch.no_grad():
        outputs = model(SAR_images=sentinel_1, optical_images=sentinel_2)

    print("\n[CROMA] Feature Extraction Results:")
    for key, val in outputs.items():
        if isinstance(val, torch.Tensor):
            print(f"  - {key}: shape={val.shape}, dtype={val.dtype}, device={val.device}")

    print("\n[CROMA] Verification SUCCESSFUL: CROMA loaded and produced cross-modal representations!")
    return True

if __name__ == '__main__':
    run_croma_verification()
