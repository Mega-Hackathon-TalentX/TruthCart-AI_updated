import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "TruthCart AI"
    assert data["team"] == "TalentX"

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "data_readiness" in data
    assert "model_readiness" in data

def test_catalogue_status_endpoint():
    response = client.get("/api/catalogue/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "records_loaded" in data

def test_chat_endpoint_answer():
    response = client.post("/api/chat", json={"message": "What is the price of TC-DEV-101?"})
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "ANSWER"
    assert len(data["citations"]) > 0
    assert "TC-DEV-101" in data["citations"][0]
    assert "1,499" in data["response_text"]

def test_chat_endpoint_empty_message():
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422 # Pydantic validation error min_length=1

def test_evaluation_run_endpoint():
    response = client.post("/api/evaluation/run", json={"dataset_name": "sample_eval_questions.json", "dry_run": True})
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions_tested"] > 0
    assert "groundedness_score" in data
    assert "citation_validity_rate" in data
