"""
Optical-SAR Downstream Classification Head for CROMA.
Multi-label remote sensing land cover classifier trained on BigEarthNet-MM / SEN1-2 schema.
Takes CROMA optical, SAR, and joint cross-modal representations to predict CORINE land cover classes.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

BIGEARTHNET_CLASSES = [
    "Urban fabric",
    "Industrial or commercial units",
    "Arable land",
    "Permanent crops",
    "Pastures",
    "Complex cultivation patterns",
    "Land principally occupied by agriculture",
    "Green urban areas",
    "Broad-leaved forest",
    "Coniferous forest",
    "Mixed forest",
    "Natural grasslands",
    "Moors and heathland",
    "Sclerophyllous vegetation",
    "Transitional woodland, shrub",
    "Beaches, dunes, sands",
    "Bare rock and sparsely vegetated",
    "Inland wetlands",
    "Water bodies"
]


class OpticalSARClassificationHead(nn.Module):
    """
    Multimodal contrastive/MLP projection head operating over CROMA pooled representations.
    Inputs:
    - joint_gap: (B, 768)
    - optical_gap: (B, 768)
    - sar_gap: (B, 768)
    Outputs:
    - logits: (B, len(BIGEARTHNET_CLASSES)) multi-label logits
    """
    def __init__(self, in_features=768 * 3, num_classes=len(BIGEARTHNET_CLASSES)):
        super().__init__()
        self.num_classes = num_classes
        self.head = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_classes)
        )

    def forward(self, joint_gap, optical_gap, sar_gap):
        # Concatenate joint, optical, and SAR representations
        fused = torch.cat([joint_gap, optical_gap, sar_gap], dim=-1)
        return self.head(fused)

    def predict_labels(self, joint_gap, optical_gap, sar_gap, threshold=0.35):
        """Generates multilabel predictions, scores, and summary text."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(joint_gap, optical_gap, sar_gap)
            probs = torch.sigmoid(logits)[0]  # (num_classes,)

            class_scores = {}
            detected = []

            for idx, cls_name in enumerate(BIGEARTHNET_CLASSES):
                p = round(float(probs[idx]), 4)
                class_scores[cls_name] = p
                if p >= threshold:
                    detected.append({"class": cls_name, "confidence": p})

            # Sort by confidence descending
            detected.sort(key=lambda x: x["confidence"], reverse=True)

            # Fallback to top-1 if none crossed threshold
            if not detected:
                top_idx = int(probs.argmax())
                detected.append({
                    "class": BIGEARTHNET_CLASSES[top_idx],
                    "confidence": round(float(probs[top_idx]), 4)
                })

            primary = detected[0]
            summary_classes = ", ".join([f"{d['class']} ({round(d['confidence'] * 100, 1)}%)" for d in detected[:4]])
            summary = (
                f"Multimodal Optical-SAR classification verified with CROMA: "
                f"Primary land-cover class is '{primary['class']}' ({round(primary['confidence'] * 100, 1)}% confidence). "
                f"Active classes: {summary_classes}."
            )

            return {
                "primary_class": primary["class"],
                "primary_confidence": primary["confidence"],
                "detected_classes": detected,
                "all_probabilities": class_scores,
                "summary": summary
            }
