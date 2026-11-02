import json

from fastapi.testclient import TestClient

from oarsight.config import Settings
from oarsight.web import create_app


def _client(tmp_path):
    settings = Settings(meta_api_key=None, baseten_api_key=None, data_dir=tmp_path)
    return TestClient(create_app(settings))


def test_index_serves_the_page(tmp_path):
    response = _client(tmp_path).get("/")
    assert response.status_code == 200
    assert "Oarsight" in response.text
    assert "ficticia o actuada" in response.text


def test_unknown_and_unsafe_session_ids_are_404(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/sessions/no-existe").status_code == 404
    assert client.get("/api/sessions/mala!id").status_code == 404
    assert client.get("/api/sessions/no-existe/audio").status_code == 404


def test_session_payload_merges_status_and_result_files(tmp_path):
    session = tmp_path / "sessions" / "demo_1"
    session.mkdir(parents=True)
    (session / "status.json").write_text(json.dumps({"status": "done", "stage": "done"}))
    (session / "metrics.json").write_text(json.dumps({"mode": "brief"}))
    payload = _client(tmp_path).get("/api/sessions/demo_1").json()
    assert payload["id"] == "demo_1"
    assert payload["status"] == "done"
    assert payload["metrics"] == {"mode": "brief"}
    assert "coding" not in payload  # missing files are simply absent


def test_page_offers_upload_and_live_recording(tmp_path):
    html = _client(tmp_path).get("/").text
    for piece in (
        "tab-upload",
        "tab-record",
        "panel-record",
        "rec-btn",
        "rec-time",
        "meterfill",
        "MediaRecorder",
        "getUserMedia",
        "Analizar grabación",
    ):
        assert piece in html


def test_clinical_font_is_self_hosted(tmp_path):
    client = _client(tmp_path)
    html = client.get("/").text
    assert "IBM Plex Sans" in html
    response = client.get("/static/fonts/ibm-plex-sans-v23-latin-regular.woff2")
    assert response.status_code == 200
    assert response.content[:4] == b"wOF2"


def test_results_use_navigable_views(tmp_path):
    html = _client(tmp_path).get("/").text
    for piece in (
        "results-nav",
        "vprev",
        "vnext",
        "vcounter",
        'data-v="report"',
        'data-v="moments"',
        'data-v="timeline"',
        'data-v="metrics"',
        'data-v="utterances"',
        "showView",
    ):
        assert piece in html


def test_empty_upload_is_rejected(tmp_path):
    response = _client(tmp_path).post("/api/sessions", files={"audio": ("vacio.mp3", b"")})
    assert response.status_code == 400
