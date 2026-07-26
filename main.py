#!/usr/bin/env python3
"""
Edge Vision MCP System
- Starts MCP Gateway with Stream, Inference, and Rule servers
- Serves React AGUI frontend on HTTP port 8080
"""
import asyncio
import json
import logging
import argparse
import os
import random
import socket
import uuid
from datetime import datetime
from aiohttp import web
from src.gateway.server import MCPGateway
from src.servers.stream_server import StreamServer
from src.servers.inference_server import InferenceServer
from src.servers.rule_server import RuleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

AGUI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "agui", "dist")


def _bind_tools(gateway, server):
    for tool_name, schema in server.get_tools().items():
        async def handler(args, _name=tool_name, _server=server):
            return await _server.handle_tool(_name, args)
        gateway.register_tool(tool_name, schema, handler)


async def get_protocol_info(args):
    return {
        "supported_versions": ["2025-11", "2026"],
        "default_version": "2026",
        "session_based_available": True,
        "stateless_available": True,
    }


async def get_system_metrics(args):
    cpu = round(10 + random.uniform(-5, 15), 1)
    tpu = round(20 + random.uniform(-10, 30), 1)
    ram = round(0.8 + random.uniform(-0.3, 1.5), 1)
    return {
        "cpu": max(0.0, min(100.0, cpu)),
        "tpu": max(0.0, min(100.0, tpu)),
        "ram": max(0.1, ram),
        "protocol": "2026",
    }


class UDPDiscovery:
    def __init__(self, host: str = "0.0.0.0", port: int = 9001, response_port: int = 9000):
        self.host = host
        self.port = port
        self.response_port = response_port
        self._transport = None
        self._advertise_ip = self._resolve_lan_ip()

    def _resolve_lan_ip(self) -> str:
        if self.host != "0.0.0.0":
            return self.host
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("192.168.1.255", 1))
            ip = sock.getsockname()[0]
            sock.close()
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        return "127.0.0.1"

    async def start(self):
        loop = asyncio.get_event_loop()
        self._transport, proto = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=(self.host, self.port),
        )
        logger.info(f"UDP discovery listening on {self.host}:{self.port}, advertising {self._advertise_ip}")

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data)
            if msg.get("type") == "discover" and msg.get("service") == "edge-vision-gateway":
                response = {
                    "type": "edge-vision-gateway",
                    "host": self._advertise_ip,
                    "port": self.response_port,
                    "protocol": "mcp",
                    "versions": ["2025-11", "2026"],
                }
                self._transport.sendto(json.dumps(response).encode(), addr)
                logger.info(f"Discovery response sent to {addr}")
        except Exception:
            pass

    def close(self):
        if self._transport:
            self._transport.close()


async def start_agui(gateway, stream_server=None):
    app = web.Application()

    async def handle_index(request):
        index_path = os.path.join(AGUI_DIR, "index.html")
        if os.path.exists(index_path):
            return web.FileResponse(index_path)
        return web.Response(text="<h1>AGUI not built. Run: npm run build in src/agui</h1>", content_type="text/html")

    async def handle_static(request):
        static_path = os.path.join(AGUI_DIR, request.match_info["path"])
        if os.path.exists(static_path) and os.path.isfile(static_path):
            return web.FileResponse(static_path)
        return web.Response(status=404)

    async def handle_rpc(request):
        body = await request.json()
        response = await gateway.process_request(body, session=None)
        if response is None:
            return web.json_response({"jsonrpc": "2.0", "id": body.get("id"), "result": None})
        return web.json_response(response.__dict__)

    async def handle_ws(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async def broadcast():
            try:
                while not ws.closed:
                    try:
                        resp = await gateway.process_request({
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "tools/call",
                            "params": {"name": "get_system_metrics", "arguments": {}}
                        }, session=None)
                        if resp and resp.result:
                            content = resp.result.get("content", [{}])[0].get("text", "{}")
                            metrics = json.loads(content)
                            await ws.send_json({"type": "metrics", **metrics})
                    except Exception:
                        pass

                    if random.random() < 0.3:
                        try:
                            alert = {
                                "type": "alert",
                                "alert_id": str(uuid.uuid4()),
                                "camera_id": f"cam_{random.randint(0, 15):02d}",
                                "rule_name": random.choice(["zone_crossing", "object_left"]),
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                            }
                            await ws.send_json(alert)
                        except Exception:
                            pass

                    if stream_server:
                        try:
                            cam_id = f"cam_{random.randint(0, 15):02d}"
                            frame = await stream_server.handle_tool("get_stream_frame", {"camera_id": cam_id})
                            await ws.send_json({"type": "frame_update", **frame})
                        except Exception:
                            pass

                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        broadcast_task = asyncio.create_task(broadcast())
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    pass
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            broadcast_task.cancel()
            await ws.close()
        return ws

    app.router.add_get("/", handle_index)
    app.router.add_get("/{path:.*}", handle_static)
    app.router.add_post("/rpc", handle_rpc)
    app.router.add_get("/ws", handle_ws)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("AGUI HTTP server listening on :8080")
    return runner


async def run_gateway(host="0.0.0.0", port=9000, serve_agui=True):
    gateway = MCPGateway(host=host, port=port)

    stream_server = StreamServer(num_cameras=16)
    inference_server = InferenceServer()
    rule_engine = RuleEngine()

    _bind_tools(gateway, stream_server)
    _bind_tools(gateway, inference_server)
    _bind_tools(gateway, rule_engine)
    gateway.register_tool("get_system_metrics", {
        "description": "Get system metrics",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }, get_system_metrics)
    gateway.register_tool("get_protocol_info", {
        "description": "Get supported MCP protocol versions and current session mode",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }, get_protocol_info)

    logger.info("Starting MCP Gateway with Stream, Inference, and Rule servers")

    mcp_server = await asyncio.start_server(gateway.handle_client, host, port)
    mcp_task = asyncio.create_task(mcp_server.serve_forever())
    logger.info(f"MCP TCP server listening on {host}:{port}")

    await stream_server.start_background_tasks()

    discovery = UDPDiscovery(host=host, response_port=port)
    await discovery.start()

    agui_runner = None
    if serve_agui:
        agui_runner = await start_agui(gateway, stream_server=stream_server)

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass
    finally:
        mcp_task.cancel()
        await stream_server.stop_background_tasks()
        discovery.close()
        if agui_runner:
            await agui_runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge Vision MCP System")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=9000, help="MCP Gateway port")
    parser.add_argument("--no-agui", action="store_true", help="Disable AGUI frontend server")
    args = parser.parse_args()
    asyncio.run(run_gateway(args.host, args.port, serve_agui=not args.no_agui))
