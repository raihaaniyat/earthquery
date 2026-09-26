import os
import torch
torch.backends.cudnn.enabled = False
from PIL import Image
from transformers import AutoImageProcessor, UperNetForSemanticSegmentation
from huggingface_hub import snapshot_download

def run_upernet_smoke_test():
    model_id = "openmmlab/upernet-convnext-tiny"
    local_dir = os.path.abspath("models/upernet-convnext-tiny")
    sample_img_path = os.path.abspath("data/samples/sample_optical.png")

    print(f"[UPerNet] Caching {model_id} locally to {local_dir}...")
    snapshot_download(repo_id=model_id, local_dir=local_dir)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[UPerNet] Loading processor and model on {device}...")

    processor = AutoImageProcessor.from_pretrained(local_dir)
    model = UperNetForSemanticSegmentation.from_pretrained(local_dir).to(device).eval()

    print("[UPerNet] Model loaded successfully.")
    print(f"[UPerNet] Pretrained Head Classes: {len(model.config.id2label)} (ADE20K scene parsing demo classes)")
    print("[UPerNet] IMPORTANT NOTE: Pretrained scene classes are generic natural-scene classes (e.g., 'tree', 'building', 'water').")
    print("[UPerNet] Dedicated water body, road network, and built-up remote-sensing segmentation REQUIRES a separately trained segmentation head.")

    # Run inference on sample optical image
    image = Image.open(sample_img_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits # (1, 150, H, W)

    # Upsample logits to original image size
    upsampled_logits = torch.nn.functional.interpolate(
        logits,
        size=image.size[::-1],
        mode="bilinear",
        align_corners=False,
    )
    pred_seg = upsampled_logits.argmax(dim=1)[0].cpu().numpy()

    print(f"[UPerNet] Output segmentation map shape: {pred_seg.shape}")
    detected_classes = [model.config.id2label[i] for i in set(pred_seg.flatten()) if i in model.config.id2label]
    print(f"[UPerNet] Demo detected classes in sample: {detected_classes[:5]}")
    print("[UPerNet] Inference smoke test completed successfully!")
    return True

if __name__ == '__main__':
    run_upernet_smoke_test()
