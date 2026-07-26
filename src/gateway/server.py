#!/usr/bin/env python3
"""
Edge Vision MCP Gateway
- JSON-RPC 2.0 over TCP
- Supports 2025-11 (session-based) and 2026 (stateless)
- Routes to stream, inference, and rule servers
"""
import asyncio
import json
import uuid
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, Awaitable
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gateway")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class Session:
    session_id: str
    protocol_version: str
    created_at: datetime
    last_active: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPRequest:
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResponse:
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Any = None
    error: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_requests: int = 1000, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clients: Dict[str, list] = {}
        self._lock = asyncio.Lock()

    async def check(self, client_id: str) -> bool:
        now = time.time()
        async with self._lock:
            timestamps = self._clients.get(client_id, [])
            timestamps = [t for t in timestamps if now - t < self.window_seconds]
            if len(timestamps) >= self.max_requests:
                return False
            timestamps.append(now)
            self._clients[client_id] = timestamps
            return True


class SessionManager:
    def __init__(self, session_ttl: int = 3600):
        self.sessions: Dict[str, Session] = {}
        self.session_ttl = session_ttl

    def create_session(self, protocol_version: str) -> Session:
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        session = Session(
            session_id=session_id,
            protocol_version=protocol_version,
            created_at=now,
            last_active=now,
        )
        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} (protocol={protocol_version})")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        session = self.sessions.get(session_id)
        if session and datetime.utcnow() - session.last_active > timedelta(seconds=self.session_ttl):
            del self.sessions[session_id]
            return None
        if session:
            session.last_active = datetime.utcnow()
        return session

    def remove_session(self, session_id: str):
        self.sessions.pop(session_id, None)

    def cleanup(self):
        now = datetime.utcnow()
        expired = [sid for sid, s in self.sessions.items()
                   if now - s.last_active > timedelta(seconds=self.session_ttl)]
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

ToolHandler = Callable[[Dict[str, Any]], Awaitable[Any]]

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, ToolHandler] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, schema: Dict[str, Any], handler: ToolHandler):
        self.tools[name] = handler
        self.schemas[name] = schema
        logger.debug(f"Registered tool: {name}")

    def get_tool(self, name: str) -> Optional[ToolHandler]:
        return self.tools.get(name)

    def list_tools(self) -> list:
        return [{"name": name, **schema} for name, schema in self.schemas.items()]


# ---------------------------------------------------------------------------
# MCP Gateway
# ---------------------------------------------------------------------------

class MCPGateway:
    def __init__(self, host: str = "0.0.0.0", port: int = 9000, rate_limit: int = 1000):
        self.host = host
        self.port = port
        self.sessions = SessionManager()
        self.registry = ToolRegistry()
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        self.sessions_lock = asyncio.Lock()
        self._setup_tools()

    def _setup_tools(self):
        # Placeholder tools will be injected by servers
        pass

    def register_tool(self, name: str, schema: Dict[str, Any], handler: ToolHandler):
        self.registry.register(name, schema, handler)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        client_id = f"{peer[0]}:{peer[1]}"
        logger.info(f"New connection from {peer}")
        session: Optional[Session] = None
        buffer = b""

        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buffer += data

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if not await self.rate_limiter.check(client_id):
                        await self._send_error(writer, None, -32000, "Rate limit exceeded")
                        continue
                    try:
                        request = json.loads(line)
                    except json.JSONDecodeError:
                        await self._send_error(writer, None, -32700, "Parse error")
                        continue

                    response = await self.process_request(request, session)
                    if response:
                        await self._send_response(writer, response)

                    if session and response and response.result is not None:
                        async with self.sessions_lock:
                            session.last_active = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error handling client {peer}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Connection closed: {peer}")

    async def process_request(self, request: Dict[str, Any], session: Optional[Session]) -> Optional[MCPResponse]:
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return await self._handle_initialize(req_id, params)
        elif method == "shutdown":
            return await self._handle_shutdown(req_id)
        elif method == "tools/list":
            return await self._handle_tools_list(req_id)
        elif method == "tools/call":
            return await self._handle_tools_call(req_id, params, session)
        else:
            return MCPResponse(id=req_id, error={"code": -32601, "message": f"Method not found: {method}"})

    async def _handle_initialize(self, req_id: Optional[str], params: Dict[str, Any]) -> MCPResponse:
        supported = params.get("supported_versions", [])
        chosen = self._negotiate_version(supported)
        protocol = "2025-11" if chosen == "2025-11" else "2026"

        session = None
        if protocol == "2025-11":
            async with self.sessions_lock:
                session = self.sessions.create_session(protocol)

        result = {
            "protocol_version": chosen,
            "capabilities": {
                "tools": {"list_changed": False},
                "sessions": protocol == "2025-11",
            },
        }
        if session:
            result["session_id"] = session.session_id

        logger.info(f"initialize: client={supported} -> chosen={chosen}")
        return MCPResponse(id=req_id, result=result)

    async def _handle_shutdown(self, req_id: Optional[str]) -> MCPResponse:
        return MCPResponse(id=req_id, result=None)

    async def _handle_tools_list(self, req_id: Optional[str]) -> MCPResponse:
        tools = self.registry.list_tools()
        return MCPResponse(id=req_id, result={"tools": tools})

    async def _handle_tools_call(self, req_id: Optional[str], params: Dict[str, Any], session: Optional[Session]) -> MCPResponse:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        session_id = params.get("session_id")

        # Session validation for 2025-11
        if session and session.protocol_version == "2025-11":
            if not session_id or session_id != session.session_id:
                return MCPResponse(
                    id=req_id,
                    error={"code": -32000, "message": "Invalid or missing session_id for 2025-11 protocol"}
                )

        handler = self.registry.get_tool(tool_name)
        if not handler:
            return MCPResponse(
                id=req_id,
                error={"code": -32601, "message": f"Tool not found: {tool_name}"}
            )

        try:
            result = await handler(arguments)
            return MCPResponse(id=req_id, result={"content": [{"type": "text", "text": json.dumps(result)}]})
        except ValueError as e:
            return MCPResponse(id=req_id, error={"code": -32602, "message": str(e)})
        except Exception as e:
            logger.error(f"Tool execution error {tool_name}: {e}")
            return MCPResponse(id=req_id, error={"code": -32603, "message": f"Internal error: {e}"})

    def _negotiate_version(self, supported: list) -> str:
        if "2026" in supported:
            return "2026"
        if "2025-11" in supported:
            return "2025-11"
        return "2026"  # Default fallback

    async def _send_response(self, writer: asyncio.StreamWriter, response: MCPResponse):
        payload = json.dumps(response.__dict__) + "\n"
        writer.write(payload.encode("utf-8"))
        await writer.drain()

    async def _send_error(self, writer: asyncio.StreamWriter, req_id: Optional[str], code: int, message: str):
        err_resp = MCPResponse(id=req_id, error={"code": code, "message": message})
        await self._send_response(writer, err_resp)

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"MCP Gateway listening on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()

    async def stop(self):
        # Cleanup logic if needed
        pass


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

async def main():
    gateway = MCPGateway()
    await gateway.start()

if __name__ == "__main__":
    asyncio.run(main())
