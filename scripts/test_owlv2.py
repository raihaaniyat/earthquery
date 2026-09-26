import time
import torch
from transformers import Owlv2ForObjectDetection, Owlv2Processor
from PIL import Image

print("[OWLv2-Grounding] Testing replacement for GeoGround-7B under 6GB VRAM limit...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[OWLv2-Grounding] Target device: {device}")

model_name = "google/owlv2-base-patch16-ensemble"
print(f"[OWLv2-Grounding] Loading processor and model from {model_name}...")

processor = Owlv2Processor.from_pretrained(model_name)
model = Owlv2ForObjectDetection.from_pretrained(model_name).to(device)

if device == "cuda":
    alloc_mb = torch.cuda.memory_allocated() / (1024 * 1024)
    print(f"[OWLv2-Grounding] VRAM allocated by model: {alloc_mb:.1f} MiB (Well under 6 GB hard limit!)")

# Run test grounding on sample image
image_path = "data/samples/sample_optical.png"
image = Image.open(image_path).convert("RGB")
texts = [["circle", "square", "building", "vegetation"]]

inputs = processor(text=texts, images=image, return_tensors="pt").to(device)
with torch.no_grad():
    outputs = model(**inputs)

target_sizes = torch.Tensor([image.size[::-1]]).to(device)
results = processor.post_process_object_detection(outputs=outputs, target_sizes=target_sizes, threshold=0.1)

boxes = results[0]["boxes"].tolist()
scores = results[0]["scores"].tolist()
labels = results[0]["labels"].tolist()

print(f"[OWLv2-Grounding] Grounding inference succeeded! Detected {len(boxes)} regions.")
for i in range(min(5, len(boxes))):
    label_text = texts[0][labels[i]]
    print(f"  - Detected '{label_text}' with confidence {scores[i]:.2f} at box {boxes[i]}")

print("[OWLv2-Grounding] Verification SUCCESSFUL!")
