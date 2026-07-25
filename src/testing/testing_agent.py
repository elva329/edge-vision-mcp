#!/usr/bin/env python3
"""
Testing Agent
- Discovers edge gateway via UDP broadcast
- Runs protocol compliance, stress, and security tests
- Reports structured JSON results
"""
import asyncio
import json
import time
import random
import logging
import argparse
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("testing-agent")

@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class MCPClient:
    def __init__(self, host: str, port: int = 9000):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.session_id: Optional[str] = None
        self.protocol_version: Optional[str] = None

    async def connect(self, protocol_version: str = "2026"):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        resp = await self._request("initialize", {"supported_versions": [protocol_version]})
        if resp and "protocol_version" in resp:
            self.protocol_version = resp["protocol_version"]
            self.session_id = resp.get("session_id")
        return resp

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.writer = None
            self.reader = None

    async def call(self, tool: str, arguments: Dict[str, Any]) -> Any:
        params = {"name": tool, "arguments": arguments}
        if self.session_id:
            params["session_id"] = self.session_id
        resp = await self._request("tools/call", params)
        if resp and "content" in resp and resp["content"]:
            text = resp["content"][0].get("text", "")
            try:
                return json.loads(text)
            except Exception:
                return text
        return resp

    async def _request(self, method: str, params: Dict[str, Any]) -> Any:
        if not self.writer:
            raise ConnectionError("Not connected")
        req = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method, "params": params}
        payload = json.dumps(req) + "\n"
        self.writer.write(payload.encode("utf-8"))
        await self.writer.drain()
        line = await asyncio.wait_for(self.reader.readline(), timeout=5)
        resp = json.loads(line)
        if "error" in resp and resp["error"]:
            raise RuntimeError(resp["error"].get("message", str(resp["error"])))
        return resp.get("result")


class TestingAgent:
    def __init__(self, gateway_host: str = "192.168.1.10", port: int = 9000):
        self.gateway_host = gateway_host
        self.port = port
        self.results: List[TestResult] = []

    async def discover(self) -> Optional[str]:
        class DiscoveryProtocol(asyncio.DatagramProtocol):
            def __init__(self):
                self.transport = None
                self.future = asyncio.Future()

            def connection_made(self, transport):
                self.transport = transport

            def datagram_received(self, data, addr):
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "edge-vision-gateway":
                        self.future.set_result(msg["host"])
                except Exception:
                    pass

        loop = asyncio.get_event_loop()
        transport, proto = await loop.create_datagram_endpoint(
            DiscoveryProtocol, local_addr=("0.0.0.0", 9001)
        )
        try:
            transport.sendto(
                json.dumps({"type": "discover", "service": "edge-vision-gateway"}).encode(),
                ("192.168.1.255", 9001),
            )
            host = await asyncio.wait_for(proto.future, timeout=2)
            return host
        except asyncio.TimeoutError:
            logger.warning("Discovery timeout, using configured host")
            return self.gateway_host
        finally:
            transport.close()

    async def run_tests(self) -> List[TestResult]:
        await self._run_protocol_tests()
        await self._run_stress_tests()
        await self._run_security_tests()
        return self.results

    async def _run_protocol_tests(self):
        client = MCPClient(self.gateway_host, self.port)

        # Test 2025-11 session-based
        start = time.time()
        try:
            await client.connect("2025-11")
            if client.session_id:
                self.results.append(TestResult("protocol_2025_11_session", True, (time.time() - start) * 1000, details={"session_id": client.session_id}))
            else:
                self.results.append(TestResult("protocol_2025_11_session", False, (time.time() - start) * 1000, error="No session_id returned"))
        except Exception as e:
            self.results.append(TestResult("protocol_2025_11_session", False, (time.time() - start) * 1000, error=str(e)))
        finally:
            await client.close()

        # Test 2026 stateless
        client = MCPClient(self.gateway_host, self.port)
        start = time.time()
        try:
            await client.connect("2026")
            if not client.session_id:
                self.results.append(TestResult("protocol_2026_stateless", True, (time.time() - start) * 1000))
            else:
                self.results.append(TestResult("protocol_2026_stateless", False, (time.time() - start) * 1000, error="Unexpected session_id"))
        except Exception as e:
            self.results.append(TestResult("protocol_2026_stateless", False, (time.time() - start) * 1000, error=str(e)))
        finally:
            await client.close()

        # Test missing session for 2025-11
        client = MCPClient(self.gateway_host, self.port)
        start = time.time()
        try:
            await client.connect("2025-11")
            await client.writer.write((json.dumps({"jsonrpc": "2.0", "id": 999, "method": "tools/call", "params": {"name": "list_cameras"}}) + "\n").encode())
            await client.writer.drain()
            line = await asyncio.wait_for(client.reader.readline(), timeout=2)
            resp = json.loads(line)
            has_error = "error" in resp and resp["error"] and "session" in resp["error"].get("message", "").lower()
            self.results.append(TestResult("protocol_2025_11_missing_session_rejected", has_error, (time.time() - start) * 1000, details=resp))
        except Exception as e:
            self.results.append(TestResult("protocol_2025_11_missing_session_rejected", False, (time.time() - start) * 1000, error=str(e)))
        finally:
            await client.close()

    async def _run_stress_tests(self):
        client = MCPClient(self.gateway_host, self.port)
        await client.connect("2026")

        # Concurrent frames
        start = time.time()
        tasks = [client.call("get_stream_frame", {"camera_id": f"cam_{i:02d}"}) for i in range(16)]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if not isinstance(r, Exception))
            self.results.append(TestResult("stress_16_concurrent_frames", success == 16, (time.time() - start) * 1000, details={"success": success, "total": 16}))
        except Exception as e:
            self.results.append(TestResult("stress_16_concurrent_frames", False, (time.time() - start) * 1000, error=str(e)))

        # Burst inference
        start = time.time()
        tasks = [client.call("run_inference", {"image_data": "mocked"}) for _ in range(50)]
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success = sum(1 for r in results if not isinstance(r, Exception))
            self.results.append(TestResult("stress_50_concurrent_inference", success >= 40, (time.time() - start) * 1000, details={"success": success, "total": 50}))
        except Exception as e:
            self.results.append(TestResult("stress_50_concurrent_inference", False, (time.time() - start) * 1000, error=str(e)))

        await client.close()

    async def _run_security_tests(self):
        client = MCPClient(self.gateway_host, self.port)
        await client.connect("2026")

        # Oversized payload
        start = time.time()
        try:
            await client.call("run_inference", {"image_data": "x" * 15_000_000})
            self.results.append(TestResult("security_oversized_payload_rejected", False, (time.time() - start) * 1000, error="Accepted oversized payload"))
        except Exception:
            self.results.append(TestResult("security_oversized_payload_rejected", True, (time.time() - start) * 1000))

        # Invalid camera id
        start = time.time()
        try:
            await client.call("get_stream_frame", {"camera_id": "../../etc/passwd"})
            self.results.append(TestResult("security_invalid_camera_id_rejected", False, (time.time() - start) * 1000, error="Accepted invalid camera_id"))
        except Exception:
            self.results.append(TestResult("security_invalid_camera_id_rejected", True, (time.time() - start) * 1000))

        await client.close()

    def report(self) -> Dict[str, Any]:
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        return {
            "summary": {"total": len(self.results), "passed": passed, "failed": failed},
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "duration_ms": round(r.duration_ms, 2),
                    "error": r.error,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


async def main():
    parser = argparse.ArgumentParser(description="Edge Vision MCP Testing Agent")
    parser.add_argument("--host", default="192.168.1.10", help="Gateway host")
    parser.add_argument("--port", type=int, default=9000, help="Gateway port")
    parser.add_argument("--output", default="test-report.json", help="Output report path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    agent = TestingAgent(args.host, args.port)
    logger.info(f"Discovering gateway at {args.host}...")
    host = await agent.discover()
    logger.info(f"Discovered gateway at {host}")

    results = await agent.run_tests()
    report = agent.report()
    print(json.dumps(report, indent=2))
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report written to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
