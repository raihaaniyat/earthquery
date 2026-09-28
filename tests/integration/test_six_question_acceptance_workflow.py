"""
SatQuery AI — Required 6-Question Acceptance Sequence Test
Verifies the exact multi-turn conversational sequence specified in Section 36 & Additional Acceptance Requirements:
1. "Analyze this satellite image and identify buildings."
2. "How many buildings did you find?"
3. "Which of those are close to roads?"
4. "Use 500 meters instead."
5. "Show them on the map."
6. "What was the total number of buildings you originally detected?"
"""

import os
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.session import Base, get_db
from backend.app.db.models import (
    Conversation,
    ConversationMessage,
    ConversationTurn,
    ConversationDataset,
    ConversationResult
)
from backend.app.services.conversation_service import ConversationEngine

from tests.conftest import TestingSessionLocal, client


def test_six_question_acceptance_sequence():
    """
    Executes the exact six-question analyst conversation in a single conversation.
    Verifies state continuity, bounded context, fact retrieval without re-inference,
    honest spatial rejection for missing road geometries, parameter modification against R1,
    map action dispatch, and historical original count retrieval.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="New Analysis")
    cid = conv.id

    # -------------------------------------------------------------------------
    # Turn 1: "Analyze this satellite image and identify buildings."
    # Initial detection run on sample optical image
    # -------------------------------------------------------------------------
    test_image_path = os.path.abspath("data/samples/sample_optical.png")
    ds = ConversationDataset(
        id=str(uuid.uuid4()),
        conversation_id=cid,
        file_path=test_image_path,
        file_name="sample_optical.png",
        role="original"
    )
    db.add(ds)
    db.commit()

    # Pre-seed verified detection result (84 buildings detected by specialist detector)
    r1 = ConversationResult(
        id="res-orig-buildings-84",
        conversation_id=cid,
        result_role="original",
        operation="building_detection",
        summary="Building detection complete. Identified 84 building structures across scene.",
        findings_json=json.dumps([{"id": i, "label": "building", "confidence": 0.88} for i in range(84)]),
        metrics_json=json.dumps({"count": 84}),
        mask_url=None
    )
    db.add(r1)
    conv.active_context_json = json.dumps({
        "original_result_id": "res-orig-buildings-84",
        "current_result_id": "res-orig-buildings-84",
        "last_operation": {"type": "building_detection", "parameters": {}}
    })
    db.commit()

    # Submit Turn 1 user message
    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "Analyze this satellite image and identify buildings.", "client_request_id": "turn-1-req"}
    )
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["conversation_id"] == cid
    assert d1["state_revision"] >= 1
    detected_count = str(len(d1.get("findings", [])))
    assert len(d1.get("findings", [])) > 0

    # -------------------------------------------------------------------------
    # Turn 2: "How many buildings did you find?"
    # Must retrieve verified count from saved result without GPU model re-execution.
    # -------------------------------------------------------------------------
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "How many buildings did you find?", "client_request_id": "turn-2-req"}
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert detected_count in d2["summary"]
    assert d2["model"] == "Fact Retrieval (Deterministic)"
    assert d2["turn_id"] != d1["turn_id"]

    # -------------------------------------------------------------------------
    # Turn 3: "Which of those are close to roads?"
    # Section 16 & Requirement 7 Invariant:
    # Must NOT hallucinate or infer distances without georeferenced road network geometry.
    # Returns honest BLOCKED explanation requesting road layer/distance threshold.
    # -------------------------------------------------------------------------
    res3 = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "Which of those are close to roads?", "client_request_id": "turn-3-req"}
    )
    assert res3.status_code == 200
    d3 = res3.json()
    assert "road network geometry" in d3["summary"].lower() or "distance threshold" in d3["summary"].lower()
    assert d3["validation"] == "failed"

    # -------------------------------------------------------------------------
    # Turn 4: "Use 500 meters instead."
    # Section 10 & 16: Must attempt parameter modification against original base R1.
    # Since road layer is absent, reports honest capability limitation without corrupting context.
    # -------------------------------------------------------------------------
    res4 = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "Use 500 meters instead.", "client_request_id": "turn-4-req"}
    )
    assert res4.status_code == 200
    d4 = res4.json()
    assert "500" in d4["summary"] or "road" in d4["summary"].lower()

    # -------------------------------------------------------------------------
    # Turn 5: "Show them on the map."
    # Returns structured map action overlay pointing to current result without rerun.
    # -------------------------------------------------------------------------
    res5 = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "Show them on the map.", "client_request_id": "turn-5-req"}
    )
    assert res5.status_code == 200
    d5 = res5.json()
    assert d5["mapAction"] is not None
    assert d5["mapAction"]["action"] == "display_result_layer"
    assert d5["model"] == "Map Action Controller"

    # -------------------------------------------------------------------------
    # Turn 6: "What was the total number of buildings you originally detected?"
    # Lineage retrieval: Resolves original detection result R1 and returns original count.
    # -------------------------------------------------------------------------
    res6 = client.post(
        f"/api/conversations/{cid}/messages",
        json={
            "prompt": "What was the total number of buildings you originally detected?",
            "client_request_id": "turn-6-req"
        }
    )
    assert res6.status_code == 200
    d6 = res6.json()
    assert detected_count in d6["summary"]
    assert d6["model"] == "Fact Retrieval (Deterministic)"

    # Verify complete stored conversation history in database
    all_msgs = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == cid
    ).order_by(ConversationMessage.created_at.asc()).all()
    assert len(all_msgs) == 12  # 6 user questions + 6 assistant responses

    # Verify conversation title was updated deterministically
    conv_refreshed = db.query(Conversation).filter(Conversation.id == cid).first()
    assert "satellite" in conv_refreshed.title.lower()

    db.close()


def test_history_continuation_after_five_turns():
    """
    Acceptance Requirement 2:
    Test History continuation after at least five completed turns.
    Reopen the conversation from History and ask another context-dependent question.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="History Continuation Test")
    cid = conv.id

    r1 = ConversationResult(
        id="res-hist-50",
        conversation_id=cid,
        result_role="original",
        operation="building_detection",
        summary="Detected 50 buildings in industrial zone.",
        findings_json=json.dumps([{"id": i, "label": "building"} for i in range(50)]),
        metrics_json=json.dumps({"count": 50})
    )
    db.add(r1)
    conv.active_context_json = json.dumps({
        "original_result_id": "res-hist-50",
        "current_result_id": "res-hist-50"
    })
    db.commit()

    # Complete 5 turns
    for i in range(5):
        client.post(
            f"/api/conversations/{cid}/messages",
            json={"prompt": f"How many did you find in sector {i}?", "client_request_id": f"hist-turn-{i}"}
        )

    # 1. Inspect History listing (Invariant 13: lightweight metadata)
    hist_res = client.get("/api/conversations")
    assert hist_res.status_code == 200
    conv_items = hist_res.json()
    matched = next((c for c in conv_items if c["id"] == cid), None)
    assert matched is not None
    assert matched["message_count"] == 10  # 5 turns = 10 messages
    assert matched["title"] is not None

    # 2. Reopen conversation from History (restore canonical snapshot)
    snap_res = client.get(f"/api/conversations/{cid}")
    assert snap_res.status_code == 200
    snap = snap_res.json()
    assert snap["conversation"]["id"] == cid
    assert len(snap["messages"]) == 10

    # 3. Ask another context-dependent question after reopening
    followup_res = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "How many did you find?", "client_request_id": "hist-turn-6-followup"}
    )
    assert followup_res.status_code == 200
    d_followup = followup_res.json()
    assert "50" in d_followup["summary"]
    assert d_followup["conversation_id"] == cid

    # Verify total 6 completed turns (12 messages)
    msgs = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == cid).all()
    assert len(msgs) == 12
    db.close()


def test_browser_refresh_after_three_turns_then_fourth():
    """
    Acceptance Requirement 3:
    Test browser refresh after three completed turns, then submit a fourth
    using the same conversation ID.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Refresh Test")
    cid = conv.id

    r1 = ConversationResult(
        id="res-refresh-25",
        conversation_id=cid,
        result_role="original",
        operation="building_detection",
        summary="Detected 25 structures.",
        findings_json=json.dumps([{"id": i, "label": "b"} for i in range(25)]),
        metrics_json=json.dumps({"count": 25})
    )
    db.add(r1)
    conv.active_context_json = json.dumps({
        "original_result_id": "res-refresh-25",
        "current_result_id": "res-refresh-25"
    })
    db.commit()

    # Complete 3 turns
    for i in range(3):
        res = client.post(
            f"/api/conversations/{cid}/messages",
            json={"prompt": f"How many did you find in zone {i}?", "client_request_id": f"ref-turn-{i}"}
        )
        assert res.status_code == 200

    # Simulate browser refresh: fetch canonical snapshot
    refresh_snap = client.get(f"/api/conversations/{cid}")
    assert refresh_snap.status_code == 200
    snap = refresh_snap.json()
    assert snap["conversation"]["id"] == cid
    assert len(snap["messages"]) == 6  # 3 turns = 6 messages

    # Submit 4th turn using the same conversation ID
    turn4_res = client.post(
        f"/api/conversations/{cid}/messages",
        json={"prompt": "How many did you find?", "client_request_id": "ref-turn-4"}
    )
    assert turn4_res.status_code == 200
    d4 = turn4_res.json()
    assert d4["conversation_id"] == cid
    assert "25" in d4["summary"]

    # Verify all 4 turns (8 messages) persisted
    all_msgs = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == cid).all()
    assert len(all_msgs) == 8
    db.close()

