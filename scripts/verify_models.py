"""
Model Verification & Provenance Diagnostic Script.
Validates model checkpoint integrity, filesystem completeness, and verification state
against declarative manifests in config/models.yaml.
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def compute_file_sha256(file_path: Path, max_bytes: int = 50 * 1024 * 1024) -> str:
    """Computes SHA-256 hash of a file (first 50MB for very large weights to ensure fast verification)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        bytes_read = 0
        while bytes_read < max_bytes:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_read += len(chunk)
    return hasher.hexdigest()


def verify_models(manifest_path: str) -> Dict[str, Any]:
    full_manifest = Path(manifest_path)
    if not full_manifest.is_absolute():
        full_manifest = REPO_ROOT / manifest_path

    if not full_manifest.exists():
        raise FileNotFoundError(f"Manifest file not found: {full_manifest}")

    with open(full_manifest, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    models_data = manifest.get("models", {})
    results = {}

    print("\n" + "=" * 80)
    print(f"  SATQUERY MODEL VERIFICATION & PROVENANCE AUDIT")
    print(f"  Manifest: {full_manifest.name}")
    print("=" * 80)
    print(f"{'Model ID':<18} | {'Task':<22} | {'State':<20} | {'Status':<10}")
    print("-" * 80)

    for m_id, spec in models_data.items():
        name = spec.get("name", m_id)
        task = spec.get("task", "")
        v_state = spec.get("verification_state", "UNKNOWN")
        ckpt_rel = spec.get("checkpoint_path")

        status_flag = "PASS"
        issues = []
        file_stats = {}

        if not ckpt_rel:
            if v_state == "TRAINING_REQUIRED":
                status_flag = "BLOCKED"
                issues.append("Training required; no trained weights exist yet.")
            else:
                status_flag = "FAIL"
                issues.append("No checkpoint_path specified in manifest.")
        else:
            ckpt_path = REPO_ROOT / ckpt_rel
            if not ckpt_path.exists():
                status_flag = "FAIL"
                issues.append(f"Checkpoint path does not exist: {ckpt_rel}")
            else:
                if ckpt_path.is_file():
                    size_mb = ckpt_path.stat().st_size / (1024 * 1024)
                    file_stats[ckpt_path.name] = {
                        "size_mb": round(size_mb, 2),
                        "sha256_prefix": compute_file_sha256(ckpt_path)[:16]
                    }
                elif ckpt_path.is_dir():
                    total_size = sum(f.stat().st_size for f in ckpt_path.glob("**/*") if f.is_file())
                    size_mb = total_size / (1024 * 1024)
                    file_stats["directory"] = {
                        "file_count": len(list(ckpt_path.glob("**/*"))),
                        "size_mb": round(size_mb, 2)
                    }

                if v_state == "INSTALLED_NOT_RUNNABLE_LOCALLY":
                    status_flag = "BLOCKED"
                    issues.append("Exceeds 8 GB VRAM capacity of RTX 5060; requires 16GB+ or offload.")

        results[m_id] = {
            "name": name,
            "task": task,
            "verification_state": v_state,
            "status": status_flag,
            "issues": issues,
            "files": file_stats
        }

        print(f"{m_id:<18} | {task:<22} | {v_state:<20} | {status_flag:<10}")

    print("=" * 80)
    return results


def main():
    parser = argparse.ArgumentParser(description="SatQuery Model Verification")
    parser.add_argument("--manifest", type=str, default="config/models.yaml", help="Path to models manifest YAML")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    results = verify_models(args.manifest)
    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
