"""Bleet API v1 and MCP sharing one authenticated service layer."""
import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from .config import Config
from .mcp_server import build_mcp, caller
from .repositories import Repositories
from .services import Gateway
from .state import State
from .terminal import terminal


class Enroll(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    device_name: str = Field(min_length=1, max_length=128)


class Pair(BaseModel):
    host_id: str = Field(min_length=1, max_length=128)
    output: Literal["link", "qr", "both"] = "both"


class Authentication:
    def __init__(self, app, state):
        self.app, self.state = app, state

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path = scope["path"]
        private = path.startswith("/v1/") and path != "/v1/enroll" or path == "/mcp" or path.startswith("/mcp/")
        principal = None
        if private:
            headers = dict(scope["headers"])
            authorization = headers.get(b"authorization", b"").decode("latin1")
            token = authorization[7:] if authorization.startswith("Bearer ") else ""
            principal = self.state.authenticate(token)
            if principal is None:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                return await JSONResponse({"detail": "authentication required"}, status_code=401, headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})(scope, receive, send)
        scope.setdefault("state", {})["principal"] = principal
        marker = caller.set(principal)
        async def no_store(message):
            if message["type"] == "http.response.start" and path != "/health":
                message["headers"] = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"] + [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
            await send(message)
        try:
            await self.app(scope, receive, no_store)
        finally:
            caller.reset(marker)


def check(principal, scope):
    if not principal or scope not in principal["scopes"]:
        raise HTTPException(403, "required scope is not granted")


def create_app(config: Config):
    state = State(config.state_dir / "state.db")
    gateway = Gateway(config, state)
    ssh_transport = gateway.ssh
    repositories = Repositories(config.repositories)
    mcp = build_mcp(gateway, repositories)
    attempts = defaultdict(deque)
    terminal_slots = asyncio.Semaphore(config.max_terminal_sessions)

    async def poll():
        while True:
            try:
                await gateway.snapshot()
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient collector/state failure is not evidence that hosts went offline.
                pass
            await asyncio.sleep(max(1, config.cache_seconds))

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            task = asyncio.create_task(poll())
            try:
                yield
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await ssh_transport.close()

    app = FastAPI(title="bleetd", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.state = state
    app.state.gateway = gateway
    app.state.mcp = mcp
    app.add_middleware(Authentication, state=state)

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/v1/enroll")
    async def enroll(body: Enroll, request: Request):
        # High-entropy single-use code plus bounded per-source attempts. The proxy
        # must not replace the source key with a caller-supplied forwarded header.
        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        while attempts[key] and attempts[key][0] < now - 60:
            attempts[key].popleft()
        if len(attempts[key]) >= 10:
            raise HTTPException(429, "enrollment temporarily rate limited")
        if len(attempts) > 1000:
            for old in list(attempts):
                if not attempts[old] or attempts[old][-1] < now - 60:
                    del attempts[old]
        attempts[key].append(now)
        result = state.redeem(body.code, body.device_name)
        if result is None:
            raise HTTPException(401, "invalid or expired enrollment code")
        return result

    @app.get("/v1/snapshot")
    async def snapshot(request: Request):
        check(request.state.principal, "read")
        return await gateway.snapshot()

    @app.post("/v1/t3/pair")
    async def pair(body: Pair, request: Request):
        check(request.state.principal, "t3:pair")
        try:
            return await gateway.pair(body.host_id, body.output)
        except ValueError as error:
            raise HTTPException(400, str(error)) from None

    @app.websocket("/v1/terminal")
    async def websocket_terminal(websocket: WebSocket, host_id: str, mode: str = "monitor"):
        principal = websocket.state.principal
        if not principal or "terminal:connect" not in principal["scopes"]:
            await websocket.close(code=1008)
            return
        await terminal(websocket, gateway, host_id, mode, terminal_slots)

    # SDK keeps its exact /mcp path, avoiding POST redirect behavior from a /mcp mount.
    app.mount("/", mcp.streamable_http_app())
    return app
