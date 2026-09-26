# Remote Sensing & Geospatial Datasets Guide

This document details where and how to obtain the standard remote-sensing benchmarks used by SatQuery AI. Full datasets should only be downloaded when sufficient disk storage is allocated and with approved credentials.

---

## 1. BigEarthNet & BigEarthNet-MM (Multimodal)
- **Official Portal:** [bigearth.net](https://bigearth.net/)
- **Repository / Zenodo DOIs:**
  - Sentinel-2 (Optical, 12 bands): [10.5281/zenodo.4893223](https://zenodo.org/record/4893223)
  - Sentinel-1 (SAR, VV/VH): [10.5281/zenodo.5168864](https://zenodo.org/record/5168864)
- **Split File (`BigEarthNet.txt`):** Available via official GitHub repository `https://github.com/Bifold-CMS/bigearthnet-models-and-data`.
- **Modality & Specifications:**
  - 590,326 non-overlapping patches (120x120 pixels at 10m resolution) across 10 European countries.
  - 19-class or 43-class Corine Land Cover (CLC) nomenclature.
- **Acquisition Command:**
  ```bash
  # Using official bigearthnet-patch-extractor or Zenodo CLI
  pip install zenodo_get
  zenodo_get 10.5281/zenodo.4893223
  zenodo_get 10.5281/zenodo.5168864
  ```

---

## 2. VRSBench (Visual Remote Sensing Benchmark)
- **Official Repository:** [https://github.com/Visual-Intelligence-Laboratory/VRSBench](https://github.com/Visual-Intelligence-Laboratory/VRSBench)
- **Paper:** *VRSBench: A Versatile Vision-Language Benchmark for Remote Sensing Image Understanding*
- **Contents:**
  - 29,614 high-resolution remote sensing images.
  - Multi-task annotations: Visual Question Answering (VQA), Referring Expression Comprehension (Visual Grounding), and Image Captioning.
  - Object annotations include both Horizontal Bounding Boxes (HBB) and Oriented Bounding Boxes (OBB).
- **Download Location:** Links and Hugging Face mirror hosted on [Hugging Face Datasets: VRSBench](https://huggingface.co/datasets).

---

## 3. RSVQA (Remote Sensing Visual Question Answering)
- **Official Portal:** [https://rsvqa.sylvainlobry.com/](https://rsvqa.sylvainlobry.com/)
- **Authors:** Sylvain Lobry, Diego Marcos, Devis Tuia (IEEE TGRS 2020)
- **Datasets:**
  - **RSVQA-LR (Low Resolution):** Built on Sentinel-2 imagery (10m resolution). Contains 772 images (256x256 pixels) and 77,232 question-answer pairs (presence, count, comparison).
  - **RSVQA-HR (High Resolution):** Built on aerial orthophotos (15cm resolution) over the Netherlands. Contains 10,659 images (512x512 pixels) and 1,066,316 QA pairs.
- **Acquisition Link:** Direct download scripts available from Sylvain Lobry's website upon request/registration.

---

## 4. CDVQA (Change Detection Visual Question Answering)
- **Official Repository:** [https://github.com/daifeng2016/Change-Detection-VQA](https://github.com/daifeng2016/Change-Detection-VQA)
- **Paper:** *Change Detection Visual Question Answering for Remote Sensing Imagery* (IEEE TGRS)
- **Contents:**
  - Bitemporal aerial/satellite image pairs ($T_1, T_2$) annotated with questions about changes.
  - Question types: Existence of change ("Did any building appear?"), attribute change ("What was replaced in the northwest region?"), and quantity comparison.
- **Distinction from ChangeFormer:**
  - **ChangeFormer:** Pixel-level binary change detection model that outputs a 2D segmentation mask (`0` or `1`).
  - **CDVQA:** High-level reasoning model that outputs natural language text answers describing bitemporal differences.

---

## Operational Rule for SatQuery AI:
- Never download full datasets speculatively during initial system installation.
- Use validated mini-sample batches (located in `data/samples/`) for smoke tests, unit tests, and CI/CD validation.
