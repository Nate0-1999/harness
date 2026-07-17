"""P0 FastAPI daemon: built static shell plus the literal C.7 WS seam."""

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from harness.envelope import Envelope, MessageType

DEFAULT_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
DEFAULT_WEB_ROOT = DEFAULT_WEB_DIST.parent


def _not_implemented_echo(message: Envelope) -> Envelope:
    """Return the only behavior authorized by the Agent Zero charge."""
    return message.model_copy(
        update={
            "type": MessageType.ERROR,
            "payload": "not implemented",
        }
    )


def create_app(web_dist: str | Path | None = None) -> FastAPI:
    """Create the scaffold daemon without agent or memory behavior."""
    app = FastAPI(title="Harness", version="0.0.0")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                try:
                    raw: Any = await websocket.receive_json()
                    message = Envelope.model_validate(raw)
                except (json.JSONDecodeError, ValidationError):
                    await websocket.close(
                        code=status.WS_1008_POLICY_VIOLATION,
                        reason="invalid C.7 envelope",
                    )
                    return

                response = _not_implemented_echo(message)
                await websocket.send_json(response.model_dump(mode="json", exclude_none=True))
        except WebSocketDisconnect:
            return

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
