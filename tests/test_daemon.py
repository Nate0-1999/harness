from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from harness.daemon import _build_web, create_app


def valid_envelope() -> dict[str, object]:
    return {
        "v": 1,
        "id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "ts": "2026-07-17T12:00:00Z",
        "machine_id": "machine-1",
        "agent_id": "agent-1",
        "thread_id": "thread-1",
        "type": "prompt.submit",
        "payload": {"prompt": "hello"},
    }


def test_serves_built_web_static(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Harness shell</h1>", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Harness shell" in response.text


def test_missing_web_build_is_explicit(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 503
    assert response.text == "web build missing; build web/ before starting harness"


def test_dev_build_uses_locked_install_before_vite_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], Path, bool]] = []

    def record(command: list[str], *, cwd: Path, check: bool) -> None:
        calls.append((command, cwd, check))

    monkeypatch.setattr("harness.daemon.subprocess.run", record)

    _build_web(tmp_path)

    assert calls == [
        (["npm", "ci"], tmp_path, True),
        (["npm", "run", "build"], tmp_path, True),
    ]


def test_ws_returns_same_shaped_not_implemented_error(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    incoming = valid_envelope()

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(incoming)
        response = websocket.receive_json()

    assert response == {
        **incoming,
        "ts": "2026-07-17T12:00:00Z",
        "type": "error",
        "payload": "not implemented",
    }


def test_ws_rejects_malformed_envelope(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    malformed = valid_envelope()
    malformed["v"] = 2

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(malformed)
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert caught.value.reason == "invalid C.7 envelope"
