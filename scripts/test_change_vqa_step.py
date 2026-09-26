import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.tasks.inference_tasks import execute_change_vqa_task

print("Testing execute_change_vqa_task directly...")
t1_path = "data/samples/sample_optical.png"
t2_path = "data/samples/sample_optical.png"
prompt = "What changed between these two acquisition dates?"

res = execute_change_vqa_task(image_t1_path=t1_path, image_t2_path=t2_path, prompt=prompt)
print("Execution result:")
print(f"Success: {res.get('success')}")
print(f"Step key: {res.get('step_key')}")
print(f"Metrics: {res.get('metrics')}")
meta = res.get("output_metadata", {})
print(f"Model: {meta.get('model')}")
print(f"Question: {meta.get('question')}")
print(f"Answer: {meta.get('answer')}")
print(f"Change detected: {meta.get('change_detected')}")
print(f"Change category: {meta.get('change_category')}")
print(f"Confidence: {meta.get('confidence')}")
print(f"VRAM Allocated: {meta.get('vram_allocated_mb')} MB")
