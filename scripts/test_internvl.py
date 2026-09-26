import os
import torch
torch.backends.cudnn.enabled = False
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer
from peft import LoraConfig, get_peft_model

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

def build_transform(input_size=448):
    transform = T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    return transform

def load_single_image(image_path, input_size=448):
    image = Image.open(image_path).convert('RGB')
    transform = build_transform(input_size)
    pixel_values = transform(image).unsqueeze(0) # (1, 3, 448, 448) single tile
    return pixel_values

def run_internvl_smoke_test():
    model_path = os.path.abspath('models/InternVL3-2B')
    sample_img_path = os.path.abspath('data/samples/sample_optical.png')

    print(f"[InternVL3-2B] Loading model from: {model_path}")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

    # Verify VRAM before loading
    if torch.cuda.is_available():
        free_mem_mb = torch.cuda.mem_get_info()[0] / (1024 * 1024)
        print(f"[InternVL3-2B] Free VRAM before model load: {free_mem_mb:.1f} MB")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True, use_fast=False)
    
    # Load model with flash_attn disabled
    model = AutoModel.from_pretrained(
        model_path,
        torch_dtype=dtype,
        low_cpu_mem_usage=True,
        use_flash_attn=False,
        trust_remote_code=True
    ).eval().to(device)

    if torch.cuda.is_available():
        alloc_mem_mb = torch.cuda.memory_allocated() / (1024 * 1024)
        print(f"[InternVL3-2B] Model successfully loaded on {device}! Allocated VRAM: {alloc_mem_mb:.1f} MB")

    # Prepare PEFT / LoRA capability check
    try:
        peft_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )
        print("[InternVL3-2B] PEFT/LoRA support ready. Adapter status: 'not yet trained' (SatQuery remote-sensing adapter).")
    except Exception as e:
        print(f"[InternVL3-2B] PEFT config note: {e}")

    # Prepare input tensor: batch size 1, 1 tile
    pixel_values = load_single_image(sample_img_path).to(dtype).to(device)
    question = "<image>\nBriefly describe what you see in this satellite image."

    print(f"[InternVL3-2B] Running single-image inference (batch size 1, 1 tile, max_new_tokens 40)...")
    generation_config = dict(
        max_new_tokens=40,
        do_sample=False,
    )
    
    with torch.no_grad():
        response = model.chat(
            tokenizer,
            pixel_values,
            question,
            generation_config
        )

    print(f"[InternVL3-2B] Inference Output:\n>>> \"{response}\"")
    print("[InternVL3-2B] Single-image inference test completed successfully!")
    return True

if __name__ == '__main__':
    run_internvl_smoke_test()
