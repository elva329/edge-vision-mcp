import asyncio
import json
import time
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gateway.server import MCPGateway, SessionManager
from src.servers.stream_server import StreamServer
from src.servers.inference_server import InferenceServer
from src.servers.rule_server import RuleEngine


@pytest.fixture
async def gateway():
    gw = MCPGateway(host="127.0.0.1", port=9001)
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

    server = await asyncio.start_server(gw.handle_client, "127.0.0.1", 9001)
    await asyncio.sleep(0.1)
    yield gw, server, stream, inference, rule
    server.close()
    await server.wait_closed()


async def make_request(reader, writer, method, params=None, session_id=None):
    req = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method, "params": params or {}}
    if session_id:
        req["params"]["session_id"] = session_id
    writer.write((json.dumps(req) + "\n").encode())
    await writer.drain()
    line = await asyncio.wait_for(reader.readline(), timeout=5)
    return json.loads(line)


@pytest.mark.asyncio
async def test_concurrent_stream_frame_requests(gateway):
    gw, server, stream, inference, rule = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9001)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    tasks = []
    for i in range(16):
        for _ in range(10):
            tasks.append(make_request(reader, writer, "tools/call",
                                      {"name": "get_stream_frame", "arguments": {"camera_id": f"cam_{i:02d}"}},
                                      session_id))

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration_ms = (time.time() - start) * 1000

    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"{len(errors)} requests failed"
    assert duration_ms < 5000, f"Concurrent requests took too long: {duration_ms}ms"

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_concurrent_inference_requests(gateway):
    gw, server, stream, inference, rule = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9001)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    tasks = []
    for _ in range(50):
        tasks.append(make_request(reader, writer, "tools/call",
                                  {"name": "run_inference", "arguments": {"image_data": "mock"}},
                                  session_id))

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration_ms = (time.time() - start) * 1000

    errors = [r for r in results if isinstance(r, Exception)]
    success = len(results) - len(errors)
    assert success >= 40, f"Only {success}/50 inference requests succeeded"
    assert duration_ms < 10000, f"Inference burst took too long: {duration_ms}ms"

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_high_throughput_list_cameras(gateway):
    gw, server, stream, inference, rule = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9001)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    start = time.time()
    for _ in range(100):
        resp = await make_request(reader, writer, "tools/call",
                                  {"name": "list_cameras", "arguments": {}}, session_id)
    duration_ms = (time.time() - start) * 1000

    assert duration_ms < 2000, f"100 list_cameras calls took too long: {duration_ms}ms"
    assert resp.get("result") is not None

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_p95_latency_under_load(gateway):
    gw, server, stream, inference, rule = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9001)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    latencies = []
    for i in range(20):
        start = time.time()
        await make_request(reader, writer, "tools/call",
                           {"name": "get_stream_frame", "arguments": {"camera_id": f"cam_{i % 16:02d}"}},
                           session_id)
        latencies.append((time.time() - start) * 1000)

    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95 = latencies[p95_index]
    assert p95 < 500, f"P95 latency {p95}ms exceeds 500ms threshold"

    writer.close()
    await writer.wait_closed()


@pytest.mark.asyncio
async def test_session_cleanup_expired_sessions(gateway):
    gw, server, stream, inference, rule = gateway
    session = gw.sessions.create_session("2025-11")
    assert gw.sessions.get_session(session.session_id) is not None

    gw.sessions.session_ttl = 0
    gw.sessions.cleanup()
    assert gw.sessions.get_session(session.session_id) is None


@pytest.mark.asyncio
async def test_16_camera_health_checks(gateway):
    gw, server, stream, inference, rule = gateway
    reader, writer = await asyncio.open_connection("127.0.0.1", 9001)
    resp = await make_request(reader, writer, "initialize", {"supported_versions": ["2026"]})
    session_id = resp.get("result", {}).get("session_id")

    tasks = []
    for i in range(16):
        tasks.append(make_request(reader, writer, "tools/call",
                                  {"name": "get_stream_health", "arguments": {"camera_id": f"cam_{i:02d}"}},
                                  session_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"{len(errors)} health checks failed"

    writer.close()
    await writer.wait_closed()