import os
import sys
import torch
import numpy as np
from PIL import Image

# Add ChangeFormer repo to sys.path
changeformer_repo = os.path.abspath('models/ChangeFormer_repo')
if changeformer_repo not in sys.path:
    sys.path.insert(0, changeformer_repo)

from models.ChangeFormer import ChangeFormerV6

def run_changeformer_verification():
    ckpt_path = os.path.abspath(
        'models/ChangeFormer/CD_ChangeFormerV6_LEVIR_b16_lr0.0001_adamw_train_test_200_linear_ce_multi_train_True_multi_infer_False_shuffle_AB_False_embed_dim_256/best_ckpt.pt'
    )
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"ChangeFormer checkpoint not found: {ckpt_path}")

    print(f"[ChangeFormerV6] Using isolated environment: satquery-changeformer")
    print(f"[ChangeFormerV6] Loading weights from: {ckpt_path}")
    
    # Initialize ChangeFormerV6 architecture (LEVIR-CD config: embed_dim=256, input_nc=3, output_nc=2)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[ChangeFormerV6] Target device: {device}")

    model = ChangeFormerV6(input_nc=3, output_nc=2, embed_dim=256)
    
    # Load state dict
    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    state_dict = checkpoint['model_G_state_dict'] if 'model_G_state_dict' in checkpoint else checkpoint
    
    # Strip potential 'module.' prefix from DataParallel training
    clean_state_dict = {}
    for k, v in state_dict.items():
        name = k[7:] if k.startswith('module.') else k
        clean_state_dict[name] = v
        
    model.load_state_dict(clean_state_dict, strict=True)
    model.to(device).eval()
    print("[ChangeFormerV6] Model architecture and weights loaded successfully.")

    # Create bitemporal sample pair: Pre-event (T1) and Post-event (T2)
    batch_size = 1
    # Normalized image tensors [-1, 1] or [0, 1]
    t1 = torch.rand(batch_size, 3, 256, 256, device=device).float()
    t2 = torch.rand(batch_size, 3, 256, 256, device=device).float()

    print(f"[ChangeFormerV6] Input T1 (Pre-event) shape: {t1.shape}")
    print(f"[ChangeFormerV6] Input T2 (Post-event) shape: {t2.shape}")
    print("[ChangeFormerV6] CRITICAL FORMAT: Output is a 2D binary change mask (0=unchanged, 1=changed), NOT natural-language text.")

    with torch.no_grad():
        logits = model(t1, t2)
        # ChangeFormer produces logits or list of multi-scale outputs
        if isinstance(logits, (list, tuple)):
            logits = logits[0]
        
        prob = torch.softmax(logits, dim=1)
        pred_mask = torch.argmax(prob, dim=1).squeeze().cpu().numpy()

    print(f"[ChangeFormerV6] Output Raw Logits shape: {logits.shape}")
    print(f"[ChangeFormerV6] Output Binary Change Mask shape: {pred_mask.shape}, values: {np.unique(pred_mask)}")
    
    # Save demo prediction mask
    os.makedirs('data/samples', exist_ok=True)
    mask_img = Image.fromarray((pred_mask * 255).astype(np.uint8))
    mask_path = 'data/samples/sample_change_mask.png'
    mask_img.save(mask_path)
    print(f"[ChangeFormerV6] Sample binary change mask saved to: {mask_path}")
    print("[ChangeFormerV6] Verification SUCCESSFUL!")
    return True

if __name__ == '__main__':
    run_changeformer_verification()
