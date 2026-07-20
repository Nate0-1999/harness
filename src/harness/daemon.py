"""FastAPI daemon: built static shell plus the routed C.7 WebSocket seam."""

import argparse
import json
import subprocess
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from harness.envelope import Envelope, MessageType

DEFAULT_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
DEFAULT_WEB_ROOT = DEFAULT_WEB_DIST.parent

type EnvelopeSender = Callable[[Envelope], Awaitable[None]]
type EnvelopeHandler = Callable[[Envelope, EnvelopeSender], Awaitable[None]]


class _InvalidEnvelope(ValueError):
    """An inbound frame that cannot represent one C.7 envelope."""


def _not_implemented_echo(message: Envelope) -> Envelope:
    """Preserve the P0 fallback until a later packet supplies behavior."""
    return message.model_copy(
        update={
            "type": MessageType.ERROR,
            "payload": "not implemented",
        }
    )


async def _not_implemented_route(message: Envelope, send: EnvelopeSender) -> None:
    await send(_not_implemented_echo(message))


def _reject_json_constant(value: str) -> None:
    raise json.JSONDecodeError("non-standard JSON constant", value, 0)


def _parse_envelope(raw: str) -> Envelope:
    try:
        decoded = json.loads(raw, parse_constant=_reject_json_constant)
        return Envelope.model_validate(decoded)
    except (ValueError, RecursionError) as exc:
        raise _InvalidEnvelope from exc


async def _receive_envelope(websocket: WebSocket) -> Envelope | None:
    event = await websocket.receive()
    if event["type"] == "websocket.disconnect":
        return None
    raw = event.get("text")
    if not isinstance(raw, str):
        raise _InvalidEnvelope
    return _parse_envelope(raw)


def create_app(
    web_dist: str | Path | None = None,
    *,
    routes: Mapping[MessageType, EnvelopeHandler] | None = None,
) -> FastAPI:
    """Create the daemon with a copied, closed C.7 message route table."""
    app = FastAPI(title="Harness", version="0.0.0")
    route_table: dict[MessageType, EnvelopeHandler] = {
        message_type: _not_implemented_route for message_type in MessageType
    }
    if routes is not None:
        for message_type, handler in routes.items():
            if not isinstance(message_type, MessageType):
                raise TypeError("route keys must be MessageType values")
            route_table[message_type] = handler

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def send(message: Envelope) -> None:
            await websocket.send_json(message.model_dump(mode="json", exclude_none=True))

        try:
            while True:
                try:
                    message = await _receive_envelope(websocket)
                except _InvalidEnvelope:
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="invalid C.7 envelope",
                    )
                    return
                if message is None:
                    return
                await route_table[message.type](message, send)
        except WebSocketDisconnect:
            return

    @app.websocket("/{path:path}")
    async def reject_unknown_websocket(websocket: WebSocket, path: str) -> None:
        await websocket.accept()
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="unknown WebSocket route",
        )

    static_root = Path(web_dist) if web_dist is not None else DEFAULT_WEB_DIST
    if (static_root / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_root, html=True), name="web")
    else:

        @app.get("/", response_class=PlainTextResponse)
        async def missing_web_build() -> PlainTextResponse:
            return PlainTextResponse(
                "web build missing; build web/ before starting harness",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    return app


def _build_web(web_root: Path = DEFAULT_WEB_ROOT) -> None:
    """Produce the built static shell that the daemon serves."""
    try:
        subprocess.run(["npm", "ci"], cwd=web_root, check=True)
        subprocess.run(["npm", "run", "build"], cwd=web_root, check=True)
    except FileNotFoundError as exc:
        raise SystemExit("npm is required for `harness dev`") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit("web install/build failed; daemon not started") from exc


def main() -> None:
    """Run the required `harness dev` developer command."""
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("command", choices=("dev",))
    args = parser.parse_args()

    if args.command == "dev":
        _build_web()
        uvicorn.run(
            "harness.daemon:create_app",
            factory=True,
            host="127.0.0.1",
            port=8765,
            reload=True,
            reload_dirs=[str(DEFAULT_WEB_ROOT.parent / "src")],
        )


if __name__ == "__main__":
    main()
