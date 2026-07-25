import asyncio
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gateway.server import MCPGateway
from src.servers.stream_server import StreamServer
from src.servers.inference_server import InferenceServer
from src.servers.rule_server import RuleEngine


@pytest.fixture
async def gateway():
    gw = MCPGateway(host="127.0.0.1", port=9002)
    stream = StreamServer(num_cameras=16)
    inference = InferenceServer()
    rule = RuleEngine()

    for tool_name, schema in stream.get_tools().items():
        async def handler(args, _n=tool_name, _s=stream):
            return await _s.handle_tool(_n, args)
        gw.register_tool(tool_name, schema, handler)

    for tool_name, schema in inference.get_tools().items():
        async def handler(args, _n=tool_name, _s=inference):
            return await _s.handle_tool(_n, args)
        gw.register_tool(tool_name, schema, handler)

    for tool_name, schema in rule.get_tools().items():
        async def handler(args, _n=tool_name, _s=rule):
            return await _s.handle_tool(_n, args)
        gw.register_tool(tool_name, schema, handler)

    server = await asyncio.start_server(gw.handle_client, "127.0.0.1", 9002)
    await asyncio.sleep(0.1)
    yield gw, server
    server.close()
    await server.wait_closed()


async def make_request(reader, writer, method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    writer.write((json.dumps(req) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=5)
    return json.loads(line)


@pytest.mark.asyncio
async def test_invalid_json_rejected(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    writer.write(b"not valid json\n")
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=2)
    resp = json.loads(line)
    assert resp.get("error") is not None
    assert resp["error"]["code"] == -32700
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_unknown_method_rejected(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "tools/unknown_method")
    assert resp.get("error") is not None
    assert resp["error"]["code"] == -32601
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_missing_session_rejected_2025_11(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2025-11"]})
    session_id = resp.get("result", {}).get("session_id")
    assert session_id is not None

    bad_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "list_cameras", "session_id": "wrong-id"}}
    writer.write((json.dumps(bad_req) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=2)
    resp = json.loads(line)
    assert resp.get("error") is not None
    assert "session" in resp["error"]["message"].lower()
    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_oversized_payload_rejected(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    bad_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "run_inference",
                          "arguments": {"image_data": "x" * 15_000_000},
                          "session_id": session_id}}
    writer.write((json.dumps(bad_req) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=2)
    resp = json.loads(line)
    assert resp.get("error") is not None

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_invalid_camera_id_rejected(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    resp = await make_request(reader, writer, "tools/call",
                               {"name": "get_stream_frame", "arguments": {"camera_id": "../../etc/passwd"},
                                "session_id": session_id})
    assert resp.get("error") is not None

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_empty_arguments_rejected(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    resp = await make_request(reader, writer, "tools/call",
                               {"name": "get_stream_frame", "arguments": {},
                                "session_id": session_id})
    assert resp.get("error") is not None

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_protocol_version_negotiation(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)

    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026", "2025-11"]})
    assert resp.get("result", {}).get("protocol_version") == "2026"

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_batch_inference_limit_enforced(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    oversized_batch = {"requests": [{"image_data": "mock"} for _ in range(20)]}
    resp = await make_request(reader, writer, "tools/call",
                               {"name": "batch_inference", "arguments": oversized_batch,
                                "session_id": session_id})
    assert resp.get("error") is not None

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_shutdown_graceful(gateway):
    gw, server = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9002)
    resp = await make_request(reader, writer, "shutdown")
    assert resp.get("result") is not None

    writer.close()
    await writer.wait_closed()