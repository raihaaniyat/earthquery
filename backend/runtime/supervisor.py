"""
Subprocess Supervisor & Cross-Process GPU Locking.
Enforces strictly serialized GPU execution using `filelock.FileLock`.
Spawns child processes in isolated Conda environments, monitors execution,
and safely terminates process trees on timeout or cancellation on Windows.
"""

import os
import sys
import json
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from filelock import FileLock, Timeout

from backend.app.config import settings
from backend.runtime.protocol import SubprocessRequest, SubprocessResponse

logger = logging.getLogger("satquery.runtime.supervisor")

# Dedicated cross-process lock file outside model directories
LOCK_DIR = Path(settings.SATQUERY_CACHE_ROOT)
LOCK_DIR.mkdir(parents=True, exist_ok=True)
GPU_LOCK_FILE = LOCK_DIR / "satquery_gpu.lock"


class ProcessSupervisor:
    @staticmethod
    def get_gpu_memory_status() -> Dict[str, int]:
        """Queries nvidia-smi for current free and total VRAM in MiB."""
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            line = res.stdout.strip().split("\n")[0]
            parts = [int(p.strip()) for p in line.split(",")]
            return {"free_mib": parts[0], "total_mib": parts[1]}
        except Exception as e:
            logger.warning(f"Unable to query nvidia-smi for VRAM: {e}")
            return {"free_mib": 8192, "total_mib": 8192}

    @staticmethod
    def run_isolated_step(
        request: SubprocessRequest,
        target_env: str,
        entrypoint_module: str,
        timeout_seconds: int = 180,
        requires_gpu: bool = True,
        required_vram_mib: int = 0
    ) -> SubprocessResponse:
        """
        Executes an isolated subprocess in the specified conda environment.
        Acquires the cross-process GPU lock if `requires_gpu=True` and enforces
        the `GPU_MIN_FREE_MIB` system reserve.
        """
        out_dir = Path(request.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        req_path = out_dir / f"req_{request.step_key}.json"
        resp_path = out_dir / f"resp_{request.step_key}.json"

        with open(req_path, "w", encoding="utf-8") as f:
            f.write(request.model_dump_json(indent=2))

        cmd = [
            settings.SATQUERY_CONDA_EXE,
            "run",
            "-n", target_env,
            "--no-capture-output",
            "python",
            "-m", entrypoint_module,
            "--request-json", str(req_path),
            "--response-json", str(resp_path)
        ]

        env = os.environ.copy()
        repo_root = Path(__file__).resolve().parent.parent.parent
        env["PYTHONPATH"] = str(repo_root)

        def _execute():
            # Check free VRAM reserve before launching GPU subprocess
            if requires_gpu:
                mem = ProcessSupervisor.get_gpu_memory_status()
                free_mib = mem["free_mib"]
                needed_mib = settings.GPU_MIN_FREE_MIB + required_vram_mib
                if free_mib < needed_mib:
                    logger.warning(
                        f"GPU Admission rejected: free VRAM ({free_mib} MiB) < required reserve + model demand ({needed_mib} MiB)"
                    )
                    return SubprocessResponse(
                        success=False,
                        job_id=request.job_id,
                        step_key=request.step_key,
                        attempt_id=request.attempt_id,
                        error_code="GPU_MEMORY_RESERVE_INSUFFICIENT",
                        error_message=(
                            f"Current free VRAM ({free_mib} MiB) is below required system reserve "
                            f"({settings.GPU_MIN_FREE_MIB} MiB reserve + {required_vram_mib} MiB task requirement)."
                        )
                    )

            t0 = time.time()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            try:
                stdout, stderr = proc.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process timed out after {timeout_seconds}s. Terminating process tree...")
                # On Windows, kill entire owned process tree
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                return SubprocessResponse(
                    success=False,
                    job_id=request.job_id,
                    step_key=request.step_key,
                    attempt_id=request.attempt_id,
                    error_code="TIMEOUT",
                    error_message=f"Execution exceeded timeout of {timeout_seconds} seconds."
                )

            # Ensure process is terminated cleanly
            if proc.poll() is None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)

            if proc.returncode != 0:
                logger.error(f"Process error (code {proc.returncode}): {stderr}")
                return SubprocessResponse(
                    success=False,
                    job_id=request.job_id,
                    step_key=request.step_key,
                    attempt_id=request.attempt_id,
                    error_code="SUBPROCESS_FAILURE",
                    error_message=f"Process exited with code {proc.returncode}: {stderr}"
                )

            if not resp_path.exists():
                return SubprocessResponse(
                    success=False,
                    job_id=request.job_id,
                    step_key=request.step_key,
                    attempt_id=request.attempt_id,
                    error_code="MISSING_OUTPUT_RESPONSE",
                    error_message="Subprocess terminated without generating response JSON."
                )

            with open(resp_path, "r", encoding="utf-8") as f:
                resp_data = json.load(f)

            return SubprocessResponse(**resp_data)

        if requires_gpu:
            logger.info("Acquiring cross-process GPU lock...")
            gpu_lock = FileLock(str(GPU_LOCK_FILE), timeout=300)
            try:
                with gpu_lock:
                    return _execute()
            except Timeout:
                return SubprocessResponse(
                    success=False,
                    job_id=request.job_id,
                    step_key=request.step_key,
                    attempt_id=request.attempt_id,
                    error_code="GPU_LOCK_TIMEOUT",
                    error_message="Could not acquire GPU lock within 300 seconds."
                )
        else:
            return _execute()



supervisor = ProcessSupervisor()
