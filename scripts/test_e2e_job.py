import httpx
import time
import json

BASE_URL = "http://127.0.0.1:8000"

# 1. Get project
projects = httpx.get(f"{BASE_URL}/api/v1/projects").json()
if not projects:
    print("No project found!")
    exit(1)

project_id = projects[0]["id"]
print(f"Using project: {project_id}")

# 2. Submit job
payload = {
    "project_id": project_id,
    "task_type": "internvl3",
    "canonical_request": {
        "task": "internvl3",
        "input_category": "benchmark",
        "prompt": "What geometric shapes and colors are present in this satellite scene?"
    },
    "user_request_text": "What geometric shapes and colors are present in this satellite scene?"
}

res = httpx.post(f"{BASE_URL}/api/v1/analysis-jobs", json=payload)
print(f"Submission status: {res.status_code}")
job_data = res.json()
job_id = job_data["job_id"]
print(f"Job ID: {job_id}, Initial status: {job_data['status']}")

# 3. Poll for completion
for i in range(20):
    time.sleep(2)
    s = httpx.get(f"{BASE_URL}/api/v1/analysis-jobs/{job_id}").json()
    print(f"[{i+1}/20] Status: {s.get('status')}, Findings: {s.get('findings_count')}, Reports: {s.get('reports_count')}")
    if s.get("status") in ("succeeded", "failed"):
        break

# 4. Fetch findings and reports
findings = httpx.get(f"{BASE_URL}/api/v1/analysis-jobs/{job_id}/findings").json()
print("\n--- FINDINGS ---")
print(json.dumps(findings, indent=2))

reports = httpx.get(f"{BASE_URL}/api/v1/analysis-jobs/{job_id}/reports").json()
print("\n--- REPORTS ---")
print(json.dumps(reports, indent=2))
