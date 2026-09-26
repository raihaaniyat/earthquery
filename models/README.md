# SatQuery AI - Models & Architecture Registry

This directory contains model architectures, adapters, tokenizers, and configuration files for the SatQuery AI multimodal Earth Observation reasoning platform.

## Model Overview

| Model | Purpose | Architecture / Backbone | Location | Weights / Checkpoints |
|---|---|---|---|---|
| **ChangeFormer** | Bitemporal Optical Change Detection | Siamese Transformer (ChangeFormerV6) | `models/ChangeFormer_repo` | `models/ChangeFormer/` (LEVIR-CD checkpoint) |
| **CROMA** | Cross-modal Optical & SAR Fusion | PretrainedCROMA Cross-Attention ViT | `models/CROMA_repo` | `models/CROMA/` (`CROMA_base.pt`) |
| **Optical-SAR Head** | Downstream Land-Cover Classification | Multi-layer Perceptron on CROMA Joint GAP | `backend/models/optical_sar_head.py` | `models/CROMA/optical_sar_head_best.pt` |
| **Change VQA** | Paired Bitemporal Spatial Reasoning | Siamese VLM Cross-Attention | `backend/models/change_vqa.py` | `models/ChangeVQA/change_vqa_best.pt` |
| **OWLv2** | Open-Vocabulary Visual Grounding | Google OWLv2 Patch-16 | `google/owlv2-base-patch16-ensemble` | Hugging Face cache / weights |
| **InternVL3-2B** | High-Resolution Earth Vision-Language | InternViT-300M + Qwen2.5-1.5B | `models/InternVL3-2B` | Hugging Face Hub (`OpenGVLab/InternVL2_5-2B`) |
| **UperNet ConvNeXt** | Semantic Segmentation (Land Cover) | ConvNeXt-Tiny + UperNet Head | `models/upernet-convnext-tiny` | Hugging Face Hub |

---

## Codebases & Adapters Tracked in Repository

- **`models/ChangeFormer_repo/`**: Complete PyTorch source code for ChangeFormer, including Siamese Transformer feature extractors, difference modules, and multi-scale attention heads.
- **`models/CROMA_repo/`**: Official source code for CROMA (Cross-sensor Optical-SAR Masked Autoencoders), enabling joint and single-sensor Earth observation embeddings.
- **`models/GeoGround_repo/`**: GeoGround reference architecture, qualitative benchmarks, and evaluation scripts.
- **`backend/models/`**:
  - `change_vqa.py`: Siamese cross-attention change VQA model architecture.
  - `optical_sar_head.py`: CROMA-representation downstream classifier.
- **`backend/runtime/`**: Isolated subprocess runtime wrappers for all models adhering to the JSON-over-stdout execution protocol.

---

## Checkpoints and Heavy Weights Storage

Heavy binary weights (`*.pt`, `*.pth`, `*.bin`, `*.safetensors`) exceeding GitHub's 100MB file limit are excluded from git tracking and can be downloaded or synced via:

1. **ChangeFormer**: Download LEVIR-CD pre-trained weights to `models/ChangeFormer/`.
2. **CROMA**: Download `CROMA_base.pt` from the official CROMA release to `models/CROMA/`.
3. **InternVL3-2B**: Download from HuggingFace (`OpenGVLab/InternVL2_5-2B`) into `models/InternVL3-2B/`.
4. **UperNet ConvNeXt**: Download from HuggingFace into `models/upernet-convnext-tiny/`.
5. **Trained Checkpoints**:
   - Change VQA: Trained via `python scripts/train_cdvqa.py`.
   - Optical-SAR Head: Trained via `python scripts/train_optical_sar_head.py`.
