import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from harness.daemon import EnvelopeSender, _build_web, create_app
from harness.envelope import Envelope, MessageType


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


def envelope_with_raw_payload(payload: str) -> str:
    raw = json.dumps({**valid_envelope(), "payload": None})
    return raw.replace('"payload": null', f'"payload": {payload}', 1)


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


def test_ws_routes_every_c7_type_to_its_handler(tmp_path: Path) -> None:
    routed: list[MessageType] = []
    routes = {}
    for message_type in MessageType:

        async def handler(
            message: Envelope,
            send: EnvelopeSender,
            *,
            expected: MessageType = message_type,
        ) -> None:
            assert message.type is expected
            routed.append(expected)
            await send(
                message.model_copy(
                    update={
                        "type": MessageType.ERROR,
                        "payload": {"routed": expected.value},
                    }
                )
            )

        routes[message_type] = handler

    client = TestClient(create_app(tmp_path, routes=routes))

    with client.websocket_connect("/ws") as websocket:
        for message_type in MessageType:
            incoming = valid_envelope()
            incoming["type"] = message_type.value
            websocket.send_json(incoming)
            response = websocket.receive_json()
            assert response["payload"] == {"routed": message_type.value}

    assert routed == list(MessageType)


def test_ws_handler_may_stream_multiple_envelopes(tmp_path: Path) -> None:
    async def stream(message: Envelope, send: EnvelopeSender) -> None:
        for index in range(2):
            await send(
                message.model_copy(
                    update={
                        "type": MessageType.RUN_DELTA,
                        "payload": {"index": index},
                    }
                )
            )

    client = TestClient(create_app(tmp_path, routes={MessageType.PROMPT_SUBMIT: stream}))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(valid_envelope())
        assert websocket.receive_json()["payload"] == {"index": 0}
        assert websocket.receive_json()["payload"] == {"index": 1}


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "null",
        "[]",
        json.dumps({**valid_envelope(), "payload": float("nan")}),
        json.dumps({key: value for key, value in valid_envelope().items() if key != "payload"}),
        json.dumps({**valid_envelope(), "v": 2}),
        json.dumps({**valid_envelope(), "type": "relay.connect"}),
        json.dumps({**valid_envelope(), "localhost": True}),
    ],
)
def test_ws_rejects_malformed_text_envelope(tmp_path: Path, raw: str) -> None:
    client = TestClient(create_app(tmp_path))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(raw)
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert caught.value.reason == "invalid C.7 envelope"


@pytest.mark.parametrize(
    "raw_payload",
    [
        pytest.param("9" * 10_000, id="integer-parser-limit"),
        pytest.param("[" * 20_000 + "0" + "]" * 20_000, id="recursive-json"),
    ],
)
def test_ws_rejects_json_parser_limits(tmp_path: Path, raw_payload: str) -> None:
    client = TestClient(create_app(tmp_path))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(envelope_with_raw_payload(raw_payload))
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert caught.value.reason == "invalid C.7 envelope"


def test_ws_rejects_binary_frame_without_routing(tmp_path: Path) -> None:
    routed = False

    async def handler(message: Envelope, send: EnvelopeSender) -> None:
        nonlocal routed
        routed = True

    client = TestClient(create_app(tmp_path, routes={MessageType.PROMPT_SUBMIT: handler}))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_bytes(json.dumps(valid_envelope()).encode())
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert caught.value.reason == "invalid C.7 envelope"
    assert routed is False


def test_ws_stops_routing_after_first_malformed_message(tmp_path: Path) -> None:
    routed: list[str] = []

    async def handler(message: Envelope, send: EnvelopeSender) -> None:
        routed.append(message.id)
        await send(message.model_copy(update={"type": MessageType.RUN_DONE}))

    client = TestClient(create_app(tmp_path, routes={MessageType.PROMPT_SUBMIT: handler}))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(valid_envelope())
        assert websocket.receive_json()["type"] == "run.done"
        websocket.send_text("{")
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert routed == ["01ARZ3NDEKTSV4RRFFQ69G5FAV"]


@pytest.mark.parametrize("path", ["/ws/", "/unknown"])
def test_built_static_mode_rejects_unknown_websocket_path(tmp_path: Path, path: str) -> None:
    (tmp_path / "index.html").write_text("<h1>Harness shell</h1>", encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(valid_envelope())
        assert websocket.receive_json()["type"] == "error"

    with client.websocket_connect(path) as websocket:
        with pytest.raises(WebSocketDisconnect) as caught:
            websocket.receive_json()

    assert caught.value.code == 1008
    assert caught.value.reason == "unknown WebSocket route"
