"""
Paired-Image Change VQA Model Architecture.
Implements Siamese Dual-Encoder + Cross-Attention Bitemporal Fusion + Natural Language Reasoning Head.
Trained on CDVQA (Change Detection Visual Question Answering).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models


CHANGE_CATEGORIES = [
    "no_change",
    "building_construction",
    "building_demolition",
    "vegetation_loss",
    "vegetation_growth",
    "road_construction",
    "water_expansion",
    "water_shrinkage"
]

CHANGE_MAGNITUDES = [
    "none",
    "minor (<10% area)",
    "moderate (10-30% area)",
    "significant (>30% area)"
]


class SiameseVisionEncoder(nn.Module):
    """Extracts deep visual features from pre- and post-event images."""
    def __init__(self, pretrained=True, embed_dim=512):
        super().__init__()
        resnet = models.resnet50(weights=models.ResNet50_Weights.DEFAULT if pretrained else None)
        self.conv1 = resnet.conv1
        self.bn1 = resnet.bn1
        self.relu = resnet.relu
        self.maxpool = resnet.maxpool
        self.layer1 = resnet.layer1
        self.layer2 = resnet.layer2
        self.layer3 = resnet.layer3
        self.layer4 = resnet.layer4
        self.avgpool = resnet.avgpool

        # Freeze early layers for speed, low VRAM, and preservation of feature representations
        for m in [self.conv1, self.bn1, self.layer1, self.layer2]:
            for p in m.parameters():
                p.requires_grad = False

        self.proj = nn.Sequential(
            nn.Linear(2048, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.GELU(),
            nn.Dropout(0.1)
        )

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return self.proj(x)


class BitemporalCrossAttentionFusion(nn.Module):
    """Fuses multi-operator temporal difference representations with question embeddings."""
    def __init__(self, embed_dim=512, num_heads=8):
        super().__init__()
        # Difference representations: [T1, T2, T2-T1, |T2-T1|, T1*T2] -> 5 * embed_dim
        self.diff_proj = nn.Sequential(
            nn.Linear(embed_dim * 5, embed_dim),
            nn.LayerNorm(embed_dim),
            nn.GELU(),
            nn.Dropout(0.1)
        )
        self.cross_attn = nn.MultiheadAttention(embed_dim=embed_dim, num_heads=num_heads, batch_first=True)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, f1, f2, q_emb):
        diff = f2 - f1
        abs_diff = torch.abs(diff)
        mult = f1 * f2
        cat = torch.cat([f1, f2, diff, abs_diff, mult], dim=-1)
        temp_feat = self.diff_proj(cat).unsqueeze(1)  # (B, 1, D)

        # Cross attention: question attends to temporal change features
        attn_out, _ = self.cross_attn(query=q_emb, key=temp_feat, value=temp_feat)
        fused = self.norm(q_emb + attn_out)
        return fused, temp_feat.squeeze(1)


class ChangeVQAModel(nn.Module):
    """
    Complete Siamese VLM Cross-Attention Model for Change Detection VQA.
    Outputs:
    - presence_logits: (B, 2) binary existence (0=unchanged, 1=changed)
    - category_logits: (B, len(CHANGE_CATEGORIES))
    - magnitude_logits: (B, len(CHANGE_MAGNITUDES))
    - reasoning_vector: (B, embed_dim) for conditional answer generation
    """
    def __init__(self, vocab_size=30522, embed_dim=512, num_heads=8):
        super().__init__()
        self.vision_encoder = SiameseVisionEncoder(pretrained=True, embed_dim=embed_dim)
        self.token_embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.q_encoder = nn.GRU(embed_dim, embed_dim // 2, batch_first=True, bidirectional=True)
        self.q_norm = nn.LayerNorm(embed_dim)

        self.fusion = BitemporalCrossAttentionFusion(embed_dim=embed_dim, num_heads=num_heads)

        # Classification heads
        self.presence_head = nn.Sequential(
            nn.Linear(embed_dim * 2, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )
        self.category_head = nn.Sequential(
            nn.Linear(embed_dim * 2, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, len(CHANGE_CATEGORIES))
        )
        self.magnitude_head = nn.Sequential(
            nn.Linear(embed_dim * 2, 128),
            nn.ReLU(),
            nn.Linear(128, len(CHANGE_MAGNITUDES))
        )

    def forward(self, img_t1, img_t2, input_ids):
        # 1. Siamese visual encoding
        f1 = self.vision_encoder(img_t1)  # (B, D)
        f2 = self.vision_encoder(img_t2)  # (B, D)

        # 2. Question text encoding
        tok_emb = self.token_embedding(input_ids)
        q_out, _ = self.q_encoder(tok_emb)
        q_emb = self.q_norm(q_out)  # (B, Seq, D)
        q_pooled = q_emb.mean(dim=1)  # (B, D)

        # 3. Cross-attention fusion
        fused_q, temp_feat = self.fusion(f1, f2, q_emb)
        fused_pooled = fused_q.mean(dim=1)  # (B, D)

        # Combined representation: [fused_q, temporal_difference]
        joint = torch.cat([fused_pooled, temp_feat], dim=-1)  # (B, 2*D)

        presence_logits = self.presence_head(joint)
        category_logits = self.category_head(joint)
        magnitude_logits = self.magnitude_head(joint)

        return {
            "presence_logits": presence_logits,
            "category_logits": category_logits,
            "magnitude_logits": magnitude_logits,
            "joint_feature": joint
        }

    def generate_answer(self, img_t1, img_t2, input_ids, question_text=""):
        """Inference method returning natural language reasoning and predictions."""
        self.eval()
        with torch.no_grad():
            preds = self.forward(img_t1, img_t2, input_ids)
            pres_prob = F.softmax(preds["presence_logits"], dim=-1)[0]
            cat_prob = F.softmax(preds["category_logits"], dim=-1)[0]
            mag_prob = F.softmax(preds["magnitude_logits"], dim=-1)[0]

            has_change = bool(pres_prob[1] > 0.5)
            cat_idx = int(cat_prob.argmax())
            mag_idx = int(mag_prob.argmax())

            cat_name = CHANGE_CATEGORIES[cat_idx]
            mag_name = CHANGE_MAGNITUDES[mag_idx]
            confidence = float(max(pres_prob[1 if has_change else 0], cat_prob[cat_idx]))

            # Natural language answer synthesis based on detected change type and query intent
            q_lower = question_text.lower()
            if not has_change or cat_name == "no_change":
                if "did" in q_lower or "has" in q_lower or "is there" in q_lower:
                    ans = "No, no significant environmental or structural change is observed between the two acquisition dates."
                else:
                    ans = "The scene remains stable with no observable land cover or building changes between T1 and T2."
            else:
                cat_desc_map = {
                    "building_construction": "new building construction and structural expansion",
                    "building_demolition": "demolition or removal of pre-existing structures",
                    "vegetation_loss": "vegetation clearing and tree cover reduction",
                    "vegetation_growth": "vegetation regrowth and canopy recovery",
                    "road_construction": "new road paving and transport corridor expansion",
                    "water_expansion": "water surface expansion and reservoir flooding",
                    "water_shrinkage": "water body contraction and shoreline retreat"
                }
                desc = cat_desc_map.get(cat_name, cat_name.replace("_", " "))

                if "did" in q_lower or "is there" in q_lower or "has" in q_lower:
                    ans = f"Yes, observable change is confirmed. Analysis detects {desc} with {mag_name}."
                elif "how many" in q_lower or "extent" in q_lower or "magnitude" in q_lower:
                    ans = f"The extent of change is {mag_name}, primarily consisting of {desc}."
                else:
                    ans = (
                        f"Bitemporal change detection reveals {desc} between T1 (pre-event) and T2 (post-event). "
                        f"The estimated affected area is {mag_name}."
                    )

            return {
                "answer": ans,
                "change_detected": has_change,
                "change_category": cat_name,
                "change_magnitude": mag_name,
                "confidence": round(confidence, 4),
                "probabilities": {
                    "presence": round(float(pres_prob[1]), 4),
                    "category": round(float(cat_prob[cat_idx]), 4)
                }
            }
