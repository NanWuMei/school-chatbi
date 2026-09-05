import os

os.environ["EMBEDDING_MODE"] = "hash"

from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import _rule_intent
from app.seed import run_seed
from app.security import hash_password, verify_password


run_seed()
client = TestClient(app)


def _login(user_id: str, password: str) -> dict:
    response = client.post("/api/v1/auth/login", json={"user_id": user_id, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_rule_intent_extracts_course():
    intent = _rule_intent("我高数多少分")
    assert intent["intent"] == "query"
    assert intent["metric"] == "score"
    assert intent["course_name"] == "高等数学"


def test_student_scope_and_chat():
    headers = _login("20230001", "student123")
    session = client.post("/api/v1/sessions", headers=headers).json()["session_id"]
    response = client.post(
        "/api/v1/chat",
        json={"session_id": session, "query": "我高数多少分"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer_type"] in {"text", "chart"}
    assert data["generated_sql"]


def test_monitor_scope_is_class_only():
    headers = _login("monitor01", "monitor123")
    response = client.post(
        "/api/v1/chat",
        json={"session_id": "scope-test", "query": "各班平均分对比"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer_type"] == "chart"
    assert len(data["data_rows"]) == 1
    assert data["data_rows"][0]["class_id"] == "class_2301"


def test_counselor_risk_warning():
    headers = _login("counselor01", "counselor123")
    response = client.post("/api/v1/skills/run", json={"skill": "risk_warning"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["answer_type"] == "report"
    assert data["data_rows"]


def test_new_analysis_skills():
    headers = _login("counselor01", "counselor123")
    for skill in ["class_compare", "course_deep", "trend_compare", "group_diff"]:
        response = client.post("/api/v1/skills/run", json={"skill": skill}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["answer_type"] == "report"
        assert data["data_rows"]


def test_student_skill_permission():
    headers = _login("20230001", "student123")
    response = client.post("/api/v1/skills/run", json={"skill": "class_compare"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["answer_type"] == "error"
    assert response.json()["text"] == "您没有权限查看"


def test_feedback_roundtrip():
    headers = _login("counselor01", "counselor123")
    session = client.post("/api/v1/sessions", headers=headers).json()["session_id"]
    chat = client.post(
        "/api/v1/chat",
        json={"session_id": session, "query": "我们班挂科率是多少"},
        headers=headers,
    )
    message_id = chat.json()["message_id"]
    feedback = client.post(
        "/api/v1/feedback",
        json={"message_id": message_id, "feedback": -1, "feedback_reason": "数据不准确"},
        headers=headers,
    )
    assert feedback.status_code == 200
    assert feedback.json()["feedback"] == -1
    listing = client.get("/api/v1/feedback", headers=headers)
    assert listing.status_code == 200
    assert listing.json()
