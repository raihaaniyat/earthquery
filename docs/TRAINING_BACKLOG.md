# SatQuery AI — Scientific Model Training Backlog

Prepared: 26 September 2026  
Target Hardware: RTX 5060 Laptop (8 GB VRAM, Blackwell CC 12.0)  
Working Architecture: Process-Isolated Antigravity Backend

---

## 1. Overview and Separation of Concerns

The operational backend infrastructure is functional, verified, and running natively under Windows processes with containerized/local fallbacks. Model execution is strictly decoupled from API and queue lifecycles.

Per the SatQuery Engineering Specification, scientific capability training is tracked separately from backend software delivery. No placeholder, randomly initialized layer, or hallucinated text output is permitted in lieu of real trained weights.

The tasks below represent the scientific training roadmap to transition blocked or demo-only capabilities into fully verified remote sensing models.

---

## 2. Capability Training Roadmap

| Capability / Task | Target Architecture | Dataset & Licenses | Verification Acceptance Criteria | Hardware / VRAM Budget |
| :--- | :--- | :--- | :--- | :--- |
| **Satellite VQA & Captioning Adaptation** | InternVL3-2B + LoRA / PEFT | RSVQA, RSICD, or NWPU-Captions (Open Research Licenses) | Held-out validation BLEU-4 / CIDEr metrics; domain vocabulary verification; reproducible checkpoint hash. | Frozen ViT backbone + LoRA (rank 8, alpha 16) on Qwen2.5-2B LLM. Fits within 6.5 GB VRAM on RTX 5060. |
| **Optical–SAR Land-Cover Classification Head** | Dual CROMA ViT-B Encoders + MLP / Contrastive Classifier | BigEarthNet-MM (Sentinel-1 & Sentinel-2 paired tiles) | Multilabel macro F1 score > 0.75 on held-out geographic tiles; calibrated probabilities; no leakage between splits. | Frozen CROMA representation extraction (batch size 16, 2.5 GB VRAM) + lightweight projection head training. |
| **Satellite Land-Cover Semantic Segmentation** | UPerNet ConvNeXt-Tiny with Satellite Head | LandCoverNet, SpaceNet, or LoveDA (Permissive licenses) | Mean IoU across primary Earth classes (Water, Vegetation, Built-up, Bare Soil, Agriculture); replaces ADE20K demo mapping. | ConvNeXt backbone with selective layer unfreezing; 512x512 patches with gradient accumulation; ~5.5 GB VRAM. |
| **Paired-Image Change VQA** | Siamese Dual-Encoder + Cross-Attention Language Head | CDVQA Dataset (Bitemporal change question-answering) | Verification of temporal directionality (Pre -> Post vs Post -> Pre); answer accuracy on held-out splits. | Siamese feature projection; batch size 1 with gradient checkpointing; ~7.0 GB VRAM. |
| **Remote Sensing Visual Grounding** | GeoGround-7B (LLaVA-1.5) | DIOR-RSVG, RSVGD | IoU@0.5 bounding box localization; requires 4-bit NF4 quantization or offloading before local execution. | Currently 13.16 GB checkpoint (exceeds 8 GB VRAM). Blocked until bitsandbytes/4-bit Blackwell quantization is validated. |

---

## 3. Dataset Acquisition & Governance Guidelines

1. **Manifest Reproducibility**:
   Every dataset must be registered in the `dataset_versions` database table with its official upstream URL, version, license, split policy, and SHA-256 manifest hash.
2. **Spatial Split Integrity**:
   Splits (train, validation, test) must be determined by geographic tile boundaries or non-overlapping regions rather than random pixel/patch slicing, preventing spatial autocorrelation leakage.
3. **Sensor Modality Contracts**:
   - Sentinel-2 optical inputs must adhere to 12-channel surface reflectance (Level-2A).
   - Sentinel-1 SAR inputs must strictly provide dual-polarization (VV + VH) calibrated gamma-0 or sigma-0 backscatter.
   - Do not synthesize SAR channels from optical bands or vice versa.
4. **Checkpoint Archival**:
   Fine-tuned weights and LoRA adapters must be stored in the immutable `satquery-models` bucket with corresponding `model_versions` database entries recording training hyperparameters and evaluation metrics.
