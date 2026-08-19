from fastapi.testclient import TestClient

from apps.api.main import app


def test_search_contract_normalizes_weights():
    client = TestClient(app)
    response = client.post(
        "/v1/search",
        json={
            "text": "minister speaking outside",
            "modalities": ["transcript", "visual"],
            "weights": {"transcript": 0.4, "visual": 0.4, "audio": 0.2},
            "limit": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["diagnostics"]["weights"] == {"transcript": 0.5, "visual": 0.5, "audio": 0.0}
    assert client.get(f"/v1/search/{body['query_id']}").status_code == 200


def test_search_contract_rejects_invalid_request():
    client = TestClient(app)
    response = client.post(
        "/v1/search",
        json={"text": "", "modalities": ["faces"], "weights": {"faces": -1}},
    )
    assert response.status_code == 422
