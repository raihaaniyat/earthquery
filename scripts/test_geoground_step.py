import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.tasks.inference_tasks import execute_geoground_task

print("Testing execute_geoground_task directly...")
image_path = "data/samples/sample_optical.png"
prompt = "locate circles and squares"

res = execute_geoground_task(image_path=image_path, prompt=prompt)
print("Execution result:")
print(f"Success: {res.get('success')}")
print(f"Step key: {res.get('step_key')}")
print(f"Metrics: {res.get('metrics')}")
meta = res.get("output_metadata", {})
print(f"Model: {meta.get('model')}")
print(f"Queries: {meta.get('queries')}")
print(f"Total detections: {meta.get('total_detections')}")
print(f"Summary: {meta.get('summary')}")
print(f"Overlay asset: {res.get('output_assets', {}).get('grounding_overlay')}")
