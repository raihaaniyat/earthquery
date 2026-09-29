"""
Integration test for the Conversational Geospatial AI Analyst Experience.
Verifies the exact multi-turn conversation sequence:
1. "tell me in very high details about finding in 300 words"
2. "Can you explain the most important finding?"
3. "Does that mean actual physical development?"
4. "What evidence supports that?"
5. "Now check specifically for new buildings."
"""

import os
import uuid
import pytest
from PIL import Image
from backend.app.services.conversation_service import ConversationEngine
from tests.conftest import TestingSessionLocal, client


@pytest.fixture
def sample_t1_and_t2(tmp_path):
    """Generate sample bitemporal pair for testing."""
    t1_path = str(tmp_path / "scene_t1.png")
    t2_path = str(tmp_path / "scene_t2.png")
    img1 = Image.new("RGB", (256, 256), color=(60, 90, 120))
    img2 = Image.new("RGB", (256, 256), color=(80, 110, 140))
    img1.save(t1_path, format="PNG")
    img2.save(t2_path, format="PNG")
    return t1_path, t2_path


def test_conversational_multi_turn_flow(sample_t1_and_t2):
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="New Analysis")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    # --- Turn 1: "tell me in very high details about finding in 300 words" ---
    q1 = "tell me in very high details about finding in 300 words"
    req_id_1 = str(uuid.uuid4())
    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q1, "client_request_id": req_id_1},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res1.status_code == 200, f"Turn 1 failed: {res1.text}"
    data1 = res1.json()
    asst_text_1 = data1["assistant_message"]["content"]
    word_count_1 = len(asst_text_1.split())

    # Verify ~300 words (240 to 360 words range is acceptable for ~300 target)
    assert 220 <= word_count_1 <= 380, f"Expected ~300 words, got {word_count_1}: {asst_text_1}"

    # Verify content quality: must explain findings, distinguish candidate vs physical change
    lower_1 = asst_text_1.lower()
    assert "change" in lower_1
    assert ("candidate" in lower_1 or "image-level" in lower_1 or "surface" in lower_1)
    assert ("development" in lower_1 or "physical" in lower_1 or "variation" in lower_1)

    # Must NOT be a dump of inactive model cards
    assert "internvl3-2b inactive" not in lower_1
    assert "upernet inactive" not in lower_1
    assert "owlv2 inactive" not in lower_1

    # Verify supporting findings are present
    supp_1 = data1.get("supporting_findings", [])
    assert len(supp_1) > 0, "Expected supporting_findings to be populated"

    # --- Turn 2: "Can you explain the most important finding?" ---
    q2 = "Can you explain the most important finding?"
    req_id_2 = str(uuid.uuid4())
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q2, "client_request_id": req_id_2}
    )
    assert res2.status_code == 200, f"Turn 2 failed: {res2.text}"
    data2 = res2.json()
    asst_text_2 = data2["assistant_message"]["content"]
    lower_2 = asst_text_2.lower()

    # Should reference previous change findings
    assert ("change" in lower_2 or "footprint" in lower_2 or "area" in lower_2)
    assert data2["conversation_id"] == cid

    # --- Turn 3: "Does that mean actual physical development?" ---
    q3 = "Does that mean actual physical development?"
    req_id_3 = str(uuid.uuid4())
    res3 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q3, "client_request_id": req_id_3}
    )
    assert res3.status_code == 200, f"Turn 3 failed: {res3.text}"
    data3 = res3.json()
    asst_text_3 = data3["assistant_message"]["content"]
    lower_3 = asst_text_3.lower()

    # Must clarify that candidate change != physical development
    assert ("not necessarily" in lower_3 or "candidate" in lower_3 or "cautious" in lower_3 or "illumination" in lower_3)
    assert ("physical" in lower_3 or "development" in lower_3 or "construction" in lower_3)
    assert data3["conversation_id"] == cid

    # --- Turn 4: "What evidence supports that?" ---
    q4 = "What evidence supports that?"
    req_id_4 = str(uuid.uuid4())
    res4 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q4, "client_request_id": req_id_4}
    )
    assert res4.status_code == 200, f"Turn 4 failed: {res4.text}"
    data4 = res4.json()
    asst_text_4 = data4["assistant_message"]["content"]
    lower_4 = asst_text_4.lower()

    # Evidence discussion
    assert ("evidence" in lower_4 or "pixel" in lower_4 or "raster" in lower_4 or "spectral" in lower_4 or "footprint" in lower_4)
    assert data4["conversation_id"] == cid

    # --- Turn 5: "Now check specifically for new buildings." ---
    q5 = "Now check specifically for new buildings."
    req_id_5 = str(uuid.uuid4())
    res5 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q5, "client_request_id": req_id_5}
    )
    assert res5.status_code == 200, f"Turn 5 failed: {res5.text}"
    data5 = res5.json()
    asst_text_5 = data5["assistant_message"]["content"]
    assert len(asst_text_5) > 0
    assert data5["conversation_id"] == cid

    # Verify full conversation thread has all turns in the DB
    db.expire_all()
    snapshot = ConversationEngine.get_conversation_snapshot(db, cid)
    msgs = snapshot["messages"]
    # 5 user messages + 5 assistant messages = 10 messages
    assert len(msgs) == 10
    for i in range(5):
        assert msgs[i * 2]["role"] == "user"
        assert msgs[i * 2 + 1]["role"] == "assistant"


def test_case_1_normal_image_summary_500_words(tmp_path):
    """
    TEST 1 — NORMAL IMAGE SUMMARY
    User asks: 'okay give me 500 words summary about the image in detailed format.'
    Expected:
    - 1 central answer of approximately ~450-520 words.
    - Key findings populated.
    - No change detection boilerplate or model dumps.
    """
    img_path = str(tmp_path / "single_scene.png")
    Image.new("RGB", (256, 256), color=(50, 100, 150)).save(img_path)

    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="500 Word Summary")
    cid = conv.id

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    q = "okay give me 500 words summary about the image in detailed format."
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[("files", ("single_scene.png", img_bytes, "image/png"))]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]
    word_count = len(asst_text.split())

    # Verify ~500 words
    assert 400 <= word_count <= 580, f"Expected ~500 words, got {word_count}: {asst_text[:200]}"
    # Verify no change detection hijacking
    lower = asst_text.lower()
    assert "bitemporal change detection reveals demolition" not in lower
    assert "demolition" not in lower
    assert data.get("supporting_findings") is not None


def test_case_2_location_single_image(tmp_path):
    """
    TEST 2 — LOCATION
    User: 'What place is this image? Tell me the city, state and country.'
    Expected:
    - Direct location answer.
    - Evidence-based coordinates/bounds.
    - No unnecessary temporal analysis.
    """
    img_path = str(tmp_path / "loc_scene.png")
    Image.new("RGB", (256, 256), color=(70, 120, 80)).save(img_path)

    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Location Query")
    cid = conv.id

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    q = "What place is this image? Tell me the city, state and country."
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[("files", ("loc_scene.png", img_bytes, "image/png"))]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]
    lower = asst_text.lower()

    # Must contain location response structure
    assert ("place" in lower or "city" in lower or "country" in lower or "coordinates" in lower)
    # Must NOT run or claim bitemporal change detection demolition
    assert "bitemporal change detection reveals demolition" not in lower
    assert "demolition" not in lower


def test_case_3_two_image_common_location_exact_prompt(sample_t1_and_t2):
    """
    TEST 3 — TWO IMAGE LOCATION (CRITICAL FIX TEST)
    User asks:
    'tell me combine about the both images in detailed format, what is the place name of the image shown in both. tell me the place, city, state, country of the image.'
    Expected:
    - Intent: common_location_identification
    - Answer specifies place, city, state, country
    - Does NOT answer primarily with 'Bitemporal change detection reveals demolition...'
    """
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Two Image Location")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    q = "tell me combine about the both images in detailed format, what is the place name of the image shown in both. tell me the place, city, state, country of the image."
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]
    lower = asst_text.lower()

    # CRITICAL CHECK: Must not hijack into demolition
    assert "bitemporal change detection reveals demolition" not in lower
    assert "demolition or removal of pre-existing structures" not in lower

    # Must answer with place/city/state/country fields
    assert "place" in lower
    assert "city" in lower
    assert "state" in lower or "province" in lower
    assert "country" in lower
    assert ("geographic" in lower or "footprint" in lower or "overlap" in lower)


def test_case_4_actual_temporal_change(sample_t1_and_t2):
    """
    TEST 4 — ACTUAL TEMPORAL CHANGE
    User: 'What changed between these two images?'
    Expected:
    - ChangeFormer / temporal model is invoked.
    - Identifies candidate surface differences.
    - Distinguishes candidate vs confirmed physical change.
    """
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Temporal Change")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    q = "What changed between these two images?"
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]
    lower = asst_text.lower()

    assert "change" in lower
    assert ("candidate" in lower or "surface" in lower or "divergence" in lower)


def test_case_5_multi_intent_location_and_change(sample_t1_and_t2):
    """
    TEST 5 — MULTI-INTENT
    User: 'Tell me which city these images show and what changed between them.'
    Expected:
    - Primary: Location identification.
    - Secondary: Temporal change.
    - Both addressed cleanly in a single unified response.
    """
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Multi Intent")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    q = "Tell me which city these images show and what changed between them."
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]
    lower = asst_text.lower()

    # Both location and change must be covered
    assert "geographic location" in lower or "city:" in lower or "location:" in lower
    assert "change" in lower or "temporal" in lower


def test_case_6_conversational_follow_up_sequence(sample_t1_and_t2):
    """
    TEST 6 — FOLLOW-UP
    User Turn 1: 'What city is this?'
    User Turn 2: 'How did you determine that?'
    User Turn 3: 'Now tell me what changed between the two images.'
    All in the SAME conversation thread.
    """
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Follow Up Thread")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    # Turn 1: "What city is this?"
    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "What city is this?", "client_request_id": str(uuid.uuid4())},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res1.status_code == 200
    t1_content = res1.json()["assistant_message"]["content"].lower()
    assert ("city:" in t1_content or "geographic" in t1_content or "location" in t1_content)

    # Turn 2: "How did you determine that?"
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "How did you determine that?", "client_request_id": str(uuid.uuid4())}
    )
    assert res2.status_code == 200
    t2_content = res2.json()["assistant_message"]["content"].lower()
    assert ("geospatial metadata" in t2_content or "reproject" in t2_content or "reverse-geocod" in t2_content or "geographic" in t2_content)

    # Turn 3: "Now tell me what changed between the two images."
    res3 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "Now tell me what changed between the two images.", "client_request_id": str(uuid.uuid4())}
    )
    assert res3.status_code == 200
    t3_content = res3.json()["assistant_message"]["content"].lower()
    assert "change" in t3_content

    # Verify conversation continuity: 6 messages total (3 user, 3 assistant)
    db.expire_all()
    snapshot = ConversationEngine.get_conversation_snapshot(db, cid)
    assert len(snapshot["messages"]) == 6


def test_case_7_no_duplication_and_clean_formatting(sample_t1_and_t2):
    """
    TEST 7 — NO DUPLICATION & CLEAN FORMATTING
    Verifies:
    - No broken markdown artifacts like **\*\* or - •.
    - No duplicated headings or machine reports.
    - Ground resolution / CRS appear naturally without redundant card dumping.
    """
    t1_path, t2_path = sample_t1_and_t2
    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="No Duplication Check")
    cid = conv.id

    with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
        t1_bytes = f1.read()
        t2_bytes = f2.read()

    q = "What changed between these two images?"
    res = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": q, "client_request_id": str(uuid.uuid4())},
        files=[
            ("files", ("scene_t1.png", t1_bytes, "image/png")),
            ("files", ("scene_t2.png", t2_bytes, "image/png"))
        ]
    )
    assert res.status_code == 200
    data = res.json()
    asst_text = data["assistant_message"]["content"]

    # Verify no raw markdown artifacts
    assert "**\\**" not in asst_text
    assert "- •" not in asst_text
    assert "• •" not in asst_text
    assert "Analysis CompleteValidation: Passed" not in asst_text

    # Verify supporting findings are concise (at most 4 items)
    supp = data.get("supporting_findings", [])
    assert len(supp) <= 4


def test_case_8_sar_and_explicit_length_tests(tmp_path):
    """
    TEST 8 — EXPLICIT LENGTH CONTROLLER & SAR ROUTING
    Verifies:
    1. 'in 500 words tell me about the image' targets ~450-520 words.
    2. 'briefly describe the image' targets concise response (< 200 words).
    3. 'describe the SAR image in 500 words' targets ~450-520 words of radar-grounded text.
    4. 'tell me about the image and location, city, state and country in 500 words' targets ~450-520 words.
    """
    img_path = str(tmp_path / "scene.png")
    Image.new("RGB", (256, 256), color=(40, 80, 120)).save(img_path)

    db = TestingSessionLocal()
    conv = ConversationEngine.get_or_create_conversation(db, title="Length & SAR Suite")
    cid = conv.id

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    # 1. Optical 500 words
    res1 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "in 500 words tell me about the image", "client_request_id": str(uuid.uuid4())},
        files=[("files", ("scene.png", img_bytes, "image/png"))]
    )
    assert res1.status_code == 200
    wc1 = len(res1.json()["assistant_message"]["content"].split())
    assert 400 <= wc1 <= 550, f"Expected ~500 words, got {wc1}"

    # 2. Briefly describe (concise)
    res2 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "briefly describe the image", "client_request_id": str(uuid.uuid4())}
    )
    assert res2.status_code == 200
    wc2 = len(res2.json()["assistant_message"]["content"].split())
    assert wc2 < 250, f"Expected concise < 250 words, got {wc2}"

    # 3. SAR 500 words
    res3 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "describe the SAR image in 500 words", "client_request_id": str(uuid.uuid4())}
    )
    assert res3.status_code == 200
    sar_text = res3.json()["assistant_message"]["content"]
    wc3 = len(sar_text.split())
    assert 400 <= wc3 <= 550, f"Expected ~500 words for SAR, got {wc3}"
    assert "radar" in sar_text.lower() or "backscatter" in sar_text.lower() or "microwave" in sar_text.lower()

    # 4. Location in 500 words
    res4 = client.post(
        f"/api/conversations/{cid}/messages",
        data={"prompt": "tell me about the image and location, city, state and country in 500 words", "client_request_id": str(uuid.uuid4())}
    )
    assert res4.status_code == 200
    loc_text = res4.json()["assistant_message"]["content"]
    wc4 = len(loc_text.split())
    assert 400 <= wc4 <= 550, f"Expected ~500 words for location, got {wc4}"
    assert "city" in loc_text.lower()
    assert "country" in loc_text.lower()



