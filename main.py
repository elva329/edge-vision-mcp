#!/usr/bin/env python3
"""
Edge Vision MCP System
- Starts MCP Gateway with Stream, Inference, and Rule servers
- Serves React AGUI frontend on HTTP port 8080
"""
import asyncio
import logging
import argparse
import os
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


async def start_agui():
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

    app.router.add_get("/", handle_index)
    app.router.add_get("/{path:.*}", handle_static)

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

    logger.info("Starting MCP Gateway with Stream, Inference, and Rule servers")

    agui_runner = None
    if serve_agui:
        agui_runner = await start_agui()

    await gateway.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge Vision MCP System")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=9000, help="MCP Gateway port")
    parser.add_argument("--no-agui", action="store_true", help="Disable AGUI frontend server")
    args = parser.parse_args()
    asyncio.run(run_gateway(args.host, args.port, serve_agui=not args.no_agui))
