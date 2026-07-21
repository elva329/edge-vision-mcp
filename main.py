#!/usr/bin/env python3
"""
Edge Vision MCP System
- Starts MCP Gateway with Stream, Inference, and Rule servers
- Optionally starts AGUI frontend server
"""
import asyncio
import logging
import argparse
from src.gateway.server import MCPGateway
from src.servers.stream_server import StreamServer
from src.servers.inference_server import InferenceServer
from src.servers.rule_server import RuleEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")


def _bind_tools(gateway: MCPGateway, server):
    for tool_name, schema in server.get_tools().items():
        # Create closure-safe handler by binding via default args
        async def handler(args, _name=tool_name, _server=server):
            return await _server.handle_tool(_name, args)
        gateway.register_tool(tool_name, schema, handler)


async def run_gateway(host: str = "0.0.0.0", port: int = 9000):
    gateway = MCPGateway(host=host, port=port)

    stream_server = StreamServer(num_cameras=16)
    inference_server = InferenceServer()
    rule_engine = RuleEngine()

    _bind_tools(gateway, stream_server)
    _bind_tools(gateway, inference_server)
    _bind_tools(gateway, rule_engine)

    logger.info("Starting MCP Gateway with Stream, Inference, and Rule servers")
    await gateway.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge Vision MCP System")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=9000, help="MCP Gateway port")
    args = parser.parse_args()
    asyncio.run(run_gateway(args.host, args.port))
