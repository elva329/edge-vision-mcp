#!/usr/bin/env python3
"""
Stream MCP Server
- Manages 16 mocked camera streams
- Returns JPEG snapshots (base64) and stream health
"""
import asyncio
import base64
import io
import time
import random
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from PIL import Image

logger = logging.getLogger("stream-server")

class MockJPEGGenerator:
    """Generates deterministic mock JPEG frames for cameras."""
    @staticmethod
    def generate(camera_id: str, width: int = 640, height: int = 480) -> bytes:
        # Create a deterministic colored frame based on camera_id
        seed = hash(camera_id) % 256
        img = Image.new("RGB", (width, height), (seed, (seed * 2) % 256, (seed * 3) % 256))
        # Add some noise / pattern
        pixels = img.load()
        for y in range(0, height, 20):
            for x in range(0, width, 20):
                pixels[x, y] = ((pixels[x, y][0] + 50) % 256,
                                (pixels[x, y][1] + 30) % 256,
                                (pixels[x, y][2] + 70) % 256)
        # Camera label
        # (skip text rendering for simplicity; color encodes camera)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50)
        return buf.getvalue()


class StreamServer:
    def __init__(self, num_cameras: int = 16):
        self.num_cameras = num_cameras
        self.cameras: Dict[str, Dict[str, Any]] = {}
        self.streaming: Dict[str, bool] = {}
        self.fps_limits = {"global": 120, "per_camera": 10}
        self._frame_counts: Dict[str, int] = {}
        self._last_frame_time: Dict[str, float] = {}
        self._init_cameras()

    def _init_cameras(self):
        for i in range(self.num_cameras):
            cam_id = f"cam_{i:02d}"
            self.cameras[cam_id] = {
                "id": cam_id,
                "resolution": "640x480",
                "fps": 10,
                "status": "live",
                "location": f"zone_{i // 4}",
            }
            self.streaming[cam_id] = True
            self._frame_counts[cam_id] = 0
            self._last_frame_time[cam_id] = 0.0

    def get_tools(self) -> Dict[str, Any]:
        return {
            "list_cameras": {
                "description": "List all cameras and their status",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "get_stream_frame": {
                "description": "Get a JPEG snapshot from a camera",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID (e.g., cam_00)"}
                    },
                    "required": ["camera_id"],
                },
            },
            "start_stream": {
                "description": "Start streaming from a camera",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID"}
                    },
                    "required": ["camera_id"],
                },
            },
            "stop_stream": {
                "description": "Stop streaming from a camera",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID"}
                    },
                    "required": ["camera_id"],
                },
            },
            "get_stream_health": {
                "description": "Get stream health metrics for a camera",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID"}
                    },
                    "required": ["camera_id"],
                },
            },
        }

    async def handle_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "list_cameras":
            return await self._list_cameras()
        elif name == "get_stream_frame":
            return await self._get_stream_frame(arguments["camera_id"])
        elif name == "start_stream":
            return await self._start_stream(arguments["camera_id"])
        elif name == "stop_stream":
            return await self._stop_stream(arguments["camera_id"])
        elif name == "get_stream_health":
            return await self._get_stream_health(arguments["camera_id"])
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def _list_cameras(self) -> list:
        return list(self.cameras.values())

    async def _get_stream_frame(self, camera_id: str) -> Dict[str, Any]:
        if camera_id not in self.cameras:
            raise ValueError(f"Camera not found: {camera_id}")
        if not self.streaming.get(camera_id, False):
            raise ValueError(f"Camera not streaming: {camera_id}")

        now = time.time()
        last = self._last_frame_time.get(camera_id, 0)
        if now - last < (1.0 / self.fps_limits["per_camera"]):
            await asyncio.sleep(0.01)  # throttle

        jpeg = MockJPEGGenerator.generate(camera_id)
        b64 = base64.b64encode(jpeg).decode("utf-8")
        self._frame_counts[camera_id] = self._frame_counts.get(camera_id, 0) + 1
        self._last_frame_time[camera_id] = time.time()

        return {
            "camera_id": camera_id,
            "format": "jpeg",
            "data": b64,
            "width": 640,
            "height": 480,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def _start_stream(self, camera_id: str) -> Dict[str, Any]:
        if camera_id not in self.cameras:
            raise ValueError(f"Camera not found: {camera_id}")
        self.streaming[camera_id] = True
        return {"camera_id": camera_id, "status": "streaming"}

    async def _stop_stream(self, camera_id: str) -> Dict[str, Any]:
        if camera_id not in self.cameras:
            raise ValueError(f"Camera not found: {camera_id}")
        self.streaming[camera_id] = False
        return {"camera_id": camera_id, "status": "stopped"}

    async def _get_stream_health(self, camera_id: str) -> Dict[str, Any]:
        if camera_id not in self.cameras:
            raise ValueError(f"Camera not found: {camera_id}")
        now = time.time()
        last = self._last_frame_time.get(camera_id, now)
        latency_ms = (now - last) * 1000 if last > 0 else 0.0
        return {
            "camera_id": camera_id,
            "status": "live" if self.streaming.get(camera_id) else "off",
            "frames_served": self._frame_counts.get(camera_id, 0),
            "last_frame_latency_ms": round(latency_ms, 2),
            "fps_limit": self.fps_limits["per_camera"],
        }


