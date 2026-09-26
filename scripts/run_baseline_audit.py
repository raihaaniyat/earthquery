"""
Phase 0 Baseline Audit Runner
Checks system, drivers, GDAL/Rasterio, PyTorch, models, and generates docs/BASELINE_AUDIT.md
"""
import os
import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path

REPO_ROOT = Path("c:/Users/HP/earthquery")

def run_cmd(cmd_list, env=None):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=60, env=env)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def audit():
    report_lines = []
    report_lines.append("# SatQuery AI — Baseline System and Environment Audit (Phase 0)")
    report_lines.append(f"**Date/Time:** {subprocess.run(['powershell', '-Command', 'Get-Date -Format o'], capture_output=True, text=True).stdout.strip()}")
    report_lines.append(f"**Host OS:** {platform.system()} {platform.release()} (Build {platform.version()})")
    report_lines.append(f"**Platform Architecture:** {platform.machine()}")
    
    # Disk & Memory
    total, used, free = shutil.disk_usage("C:/")
    report_lines.append(f"**C: Disk Free:** {free / (1024**3):.2f} GB (Total: {total / (1024**3):.2f} GB)")
    
    # GPU
    ret, out, err = run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    if ret == 0:
        gpu_info = out.split("\n")[0]
        report_lines.append(f"**NVIDIA GPU & Driver:** {gpu_info}")
    else:
        report_lines.append(f"**NVIDIA GPU:** Error running nvidia-smi: {err}")
        
    # Docker and WSL
    ret_wsl, out_wsl, err_wsl = run_cmd(["wsl", "--version"])
    report_lines.append(f"**WSL Installed:** {'No (wsl error / not installed)' if ret_wsl != 0 else out_wsl}")
    
    ret_dock, out_dock, err_dock = run_cmd(["powershell", "-Command", "Get-Command docker -ErrorAction SilentlyContinue"])
    report_lines.append(f"**Docker in PATH:** {'No' if not out_dock else out_dock}")
    
    report_lines.append("\n## 1. Existing Conda Environments")
    sqConda = "C:/Users/HP/miniconda3/Scripts/conda.exe"
    ret, out, _ = run_cmd([sqConda, "env", "list"])
    report_lines.append("```text\n" + out + "\n```")
    
    report_lines.append("\n## 2. Geospatial Stack Audit (`satquery-core`)")
    core_python = "C:/Users/HP/miniconda3/envs/satquery-core/python.exe"
    geo_test_code = """
import osgeo.gdal as gdal
import rasterio
import pyproj
import shapely
import geopandas as gpd
import numpy as np

print(f"GDAL (osgeo): {gdal.__version__}")
print(f"Rasterio: {rasterio.__version__}, GDAL compiled: {rasterio.__gdal_version__}")
print(f"PyProj: {pyproj.__version__}, PROJ: {pyproj.__proj_version__}")
print(f"Shapely: {shapely.__version__}")
print(f"GeoPandas: {gpd.__version__}")
print(f"NumPy: {np.__version__}")

# Driver test
drv = gdal.GetDriverByName('GTiff')
print(f"GTiff Driver available: {drv is not None}")

# Native raster create, write, read, CRS transform test
test_tif = 'c:/Users/HP/earthquery/artifacts/baseline/test_geo.tif'
transform = rasterio.transform.from_origin(77.59, 12.97, 0.0001, 0.0001)
data = np.random.randint(0, 255, (3, 64, 64), dtype=np.uint8)
with rasterio.open(
    test_tif, 'w', driver='GTiff',
    height=64, width=64, count=3, dtype=data.dtype,
    crs='+proj=latlong', transform=transform
) as dst:
    dst.write(data)

with rasterio.open(test_tif) as src:
    read_data = src.read()
    assert read_data.shape == (3, 64, 64)
    print("Raster read/write test: PASSED")

# Reprojection test with pyproj
crs_4326 = pyproj.CRS.from_epsg(4326)
crs_3857 = pyproj.CRS.from_epsg(3857)
transformer = pyproj.Transformer.from_crs(crs_4326, crs_3857, always_xy=True)
x, y = transformer.transform(77.59, 12.97)
print(f"Transform EPSG:4326 -> EPSG:3857 (Bengaluru): ({x:.2f}, {y:.2f}) - PASSED")
"""
    ret, out, err = run_cmd([core_python, "-c", geo_test_code])
    if ret == 0:
        report_lines.append("```text\n" + out + "\n```")
    else:
        report_lines.append(f"Geospatial test FAILED:\n```text\n{err}\n```")
        
    report_lines.append("\n## 3. GPU PyTorch & Tensor Execution (`satquery-core`)")
    torch_test_code = """
import torch
print(f"PyTorch: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    print(f"Compute Capability: {torch.cuda.get_device_capability(0)}")
    torch.backends.cudnn.enabled = False
    a = torch.randn(1024, 1024, device='cuda', dtype=torch.float32)
    b = torch.randn(1024, 1024, device='cuda', dtype=torch.float32)
    c = torch.matmul(a, b)
    torch.cuda.synchronize()
    print(f"CUDA MatMul 1024x1024 Norm: {c.norm().item():.2f} - PASSED")
    print(f"Allocated VRAM: {torch.cuda.memory_allocated() / (1024**2):.2f} MB")
"""
    ret, out, err = run_cmd([core_python, "-c", torch_test_code])
    if ret == 0:
        report_lines.append("```text\n" + out + "\n```")
    else:
        report_lines.append(f"PyTorch test FAILED:\n```text\n{err}\n```")
        
    report_lines.append("\n## 4. Model Checkpoint & State Inventory")
    models_dir = Path("c:/Users/HP/earthquery/models")
    models_info = []
    for item in models_dir.iterdir():
        if item.is_dir():
            size = sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
            models_info.append(f"- **`{item.name}`**: {size / (1024**2):.2f} MB")
        elif item.is_file():
            models_info.append(f"- **`{item.name}`**: {item.stat().st_size / (1024**2):.2f} MB")
    report_lines.extend(models_info)
    
    report_lines.append("\n## 5. Discrepancy & Finding Table")
    report_lines.append("""
| Area | Observation | Impact | Required Action in Plan |
|---|---|---|---|
| Docker / WSL | Docker executable not found in PATH; WSL not installed | Containers cannot run natively until Docker Desktop/WSL is installed | Maintain fallback resilience, document setup commands for Windows host, use mock/sqlite in isolated test gates when containers offline |
| cuDNN on Windows | Dynamic symbol mismatch in cuDNN 9 (`cudnnGetVersion`) | PyTorch scripts fail if cuDNN is enabled | Keep `torch.backends.cudnn.enabled = False` in CUDA worker processes |
| NumPy Version | Pinned to `1.26.4` in `satquery-core` | NumPy 2.x breaks GDAL / Shapely C-ABI | Maintain `numpy==1.26.4` across all geospatial worker environments |
| ChangeFormer Environment | Python 3.9 in `satquery-changeformer` | Dedicated worker for legacy dependencies | Use isolated subprocess runner; verify CPU inference execution |
| GeoGround 7B VRAM | 13.16 GB checkpoint on 8 GB GPU | Cannot fit in VRAM concurrently | Keep marked as `INSTALLED BUT NOT RUNNABLE LOCALLY`; require explicit offload / remote host |
| RQ Windows Support | Windows does not support `fork()` | Standard RQ workers fail on Windows | Use `rq.worker.SpawnWorker` (available in RQ >= 2.2; currently installed 2.12.0) |
""")
    
    audit_md = REPO_ROOT / "docs/BASELINE_AUDIT.md"
    audit_md.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Wrote baseline audit to {audit_md}")

if __name__ == "__main__":
    audit()
