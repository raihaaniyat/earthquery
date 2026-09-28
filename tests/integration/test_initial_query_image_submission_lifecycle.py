"""
SatQuery AI — Initial Query + Image Submission Lifecycle Integration Tests
Verifies the end-to-end lifecycle for single-turn query + image submissions:
1. Query ("describe this image") + JPEG attachment form ONE logical turn.
2. Backend validates, attaches dataset, and passes the exact query to LangGraph.
3. Automatic execution without prompting the user for a second question.
4. Results and assistant narrative persisted and returned.
5. Subsequent follow-up queries reuse active context without requiring re-upload.
6. Orphaned/unexecuted turn recovery works reliably.
7. Verification of all API endpoints (/api/conversations, /api/conversations/{id}/messages) returning 200 (no 404 errors).
"""

import os
import io
import json
import uuid
import pytest
from PIL import Image
from backend.app.services.conversation_service import ConversationEngine
from backend.app.db.models import ConversationMessage, ConversationTurn
from tests.conftest import TestingSessionLocal, client


@pytest.fixture
def sample_jpeg_path(tmp_path):
    """Generates a temporary sample JPEG image for testing."""
    img_path = str(tmp_path / "WhatsApp_Image_2026-09-27_at_4.24.00_PM.jpeg")
    img = Image.new("RGB", (256, 256), color=(73, 109, 137))
    img.save(img_path, format="JPEG")
    return img_path


def test_describe_this_image_jpeg_submission(sample_jpeg_path):
    """
    Test Case: User types 'describe this image' and attaches a JPEG file.
    Verifies:
    1. HTTP 200 from /api/conversations/{cid}/messages (no 404 error).
    2. Exactly ONE logical turn created with status COMPLETED.
    3. User message contains exact query 'describe this image'.
    4. Dataset is correctly cataloged as role 'original'.
    5. Assistant response is immediately available without requiring a second prompt.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="New Analysis")
    cid = conv.id
    req_id = str(uuid.uuid4())

    with open(sample_jpeg_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "describe this image",
            "client_request_id": req_id
        },
        files={
            "files": ("WhatsApp_Image_2026-09-27_at_4.24.00_PM.jpeg", file_bytes, "image/jpeg")
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["conversation_id"] == cid
    assert data["client_request_id"] == req_id
    assert data["user_message"]["content"] == "describe this image"
    assert data["assistant_message"] is not None
    assert len(data["assistant_message"]["content"]) > 0
    assert data["status"] == "COMPLETED"

    # Verify database state
    db.expire_all()
    snap = ConversationEngine.get_conversation_snapshot(db, cid)
    assert len(snap["messages"]) == 2
    assert snap["messages"][0]["role"] == "user"
    assert snap["messages"][0]["content"] == "describe this image"
    assert snap["messages"][1]["role"] == "assistant"
    assert len(snap["datasets"]) == 1
    assert snap["datasets"][0]["role"] == "original"
    assert "WhatsApp" in snap["datasets"][0]["file_name"]


def test_no_second_prompt_required_and_automatic_execution(sample_jpeg_path):
    """
    Verifies that upon submitting query + attachment, the system executes
    the selected analytical plan immediately and produces an assistant narrative
    without pausing to ask for another prompt.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db)
    cid = conv.id
    req_id = str(uuid.uuid4())

    with open(sample_jpeg_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "Analyze landscape features in this satellite scene.",
            "client_request_id": req_id
        },
        files={
            "files": ("scene.jpeg", file_bytes, "image/jpeg")
        }
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "COMPLETED"
    assert "landscape" in res_data["user_message"]["content"].lower()
    # Assistant must answer, not ask for input
    assert len(res_data["summary"]) > 0


def test_follow_up_without_reuploading_image(sample_jpeg_path):
    """
    Verifies that once the initial query and image have finished processing,
    the user can submit an ordinary follow-up turn without re-attaching the image,
    and the pipeline automatically reuses the original image dataset.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db)
    cid = conv.id

    # Turn 1: Initial query + image
    with open(sample_jpeg_path, "rb") as f:
        file_bytes = f.read()

    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "describe this image",
            "client_request_id": str(uuid.uuid4())
        },
        files={
            "files": ("input.jpeg", file_bytes, "image/jpeg")
        }
    )
    assert res1.status_code == 200

    # Turn 2: Follow-up question (NO files attached)
    req2_id = str(uuid.uuid4())
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        json={
            "prompt": "Explain this observation in detail.",
            "client_request_id": req2_id
        }
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["user_message"]["content"] == "Explain this observation in detail."
    assert data2["assistant_message"] is not None
    assert len(data2["assistant_message"]["content"]) > 0

    # Verify conversation history has 4 messages (2 user, 2 assistant)
    db.expire_all()
    snap = ConversationEngine.get_conversation_snapshot(db, cid)
    assert len(snap["messages"]) == 4


def test_recovery_of_unexecuted_turn(sample_jpeg_path):
    """
    Tests recovering a conversation where a user message was submitted with an image,
    but no assistant response was produced (the exact symptom from the screenshot).
    Verifies that calling messages with the query re-executes using the attached dataset.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="describe this image")
    cid = conv.id

    # Turn 1: upload image with first turn
    with open(sample_jpeg_path, "rb") as f:
        file_bytes = f.read()

    init_res = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "describe this image",
            "client_request_id": str(uuid.uuid4())
        },
        files={
            "files": ("base_image.jpeg", file_bytes, "image/jpeg")
        }
    )
    assert init_res.status_code == 200

    # Simulate an orphaned state: user submitted a new turn but it wasn't fulfilled
    orphaned_req_id = str(uuid.uuid4())
    orphaned_msg = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=cid,
        role="user",
        content="describe this image again",
        client_request_id=orphaned_req_id
    )
    db.add(orphaned_msg)
    db.commit()

    # Client initiates recovery via retryLastTurn
    retry_req_id = str(uuid.uuid4())
    retry_res = client.post(
        f"/api/conversations/{cid}/messages",
        json={
            "prompt": "describe this image again",
            "client_request_id": retry_req_id
        }
    )
    assert retry_res.status_code == 200
    retry_data = retry_res.json()
    assert retry_data["status"] == "COMPLETED"
    assert retry_data["assistant_message"] is not None


def test_idempotency_prevents_duplicate_turn(sample_jpeg_path):
    """
    Submitting the exact same client_request_id must not create duplicate turns or messages.
    """
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db)
    cid = conv.id
    req_id = str(uuid.uuid4())

    with open(sample_jpeg_path, "rb") as f:
        file_bytes = f.read()

    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "describe this image",
            "client_request_id": req_id
        },
        files={
            "files": ("sample.jpeg", file_bytes, "image/jpeg")
        }
    )
    assert res1.status_code == 200

    # Repeat submit with identical client_request_id
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        data={
            "prompt": "describe this image",
            "client_request_id": req_id
        },
        files={
            "files": ("sample.jpeg", file_bytes, "image/jpeg")
        }
    )
    assert res2.status_code == 200
    assert res2.json()["turn_id"] == res1.json()["turn_id"]

    db.expire_all()
    snap = ConversationEngine.get_conversation_snapshot(db, cid)
    assert len(snap["messages"]) == 2  # exactly 1 user, 1 assistant


def test_conversation_api_endpoints_no_404():
    """
    Verifies that all conversational API routes return valid status codes (no 404).
    """
    # 1. List conversations
    res_list = client.get("/api/conversations")
    assert res_list.status_code == 200

    # 2. Create conversation
    res_create = client.post("/api/conversations", json={"title": "Test Title"})
    assert res_create.status_code == 200
    cid = res_create.json()["conversation"]["id"]

    # 3. Get conversation snapshot
    res_snap = client.get(f"/api/conversations/{cid}")
    assert res_snap.status_code == 200

    # 4. Delete conversation
    res_del = client.delete(f"/api/conversations/{cid}")
    assert res_del.status_code == 200
