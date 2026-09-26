import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.tasks.inference_tasks import execute_optical_sar_task

print("Testing execute_optical_sar_task directly...")
s1_path = "data/samples/sample_sar.tif"
s2_path = "data/samples/sample_optical.png"

res = execute_optical_sar_task(sentinel_1_path=s1_path, sentinel_2_path=s2_path)
print("Execution result:")
print(f"Success: {res.get('success')}")
print(f"Step key: {res.get('step_key')}")
print(f"Metrics: {res.get('metrics')}")
meta = res.get("output_metadata", {})
print(f"Model: {meta.get('model')}")
print(f"Primary class: {meta.get('primary_class')}")
print(f"Confidence: {meta.get('confidence')}")
print(f"Detected classes: {meta.get('detected_classes')}")
print(f"Summary: {meta.get('summary')}")
print(f"VRAM Allocated: {meta.get('vram_allocated_mb')} MB")
