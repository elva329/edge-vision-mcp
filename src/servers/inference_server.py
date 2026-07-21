#!/usr/bin/env python3
"""
Inference MCP Server
- Mocked TPU inference
- Returns bounding boxes, labels, confidence
"""
import asyncio
import time
import random
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("inference-server")

class MockTPUInference:
    """Simulates TPU inference with realistic latency."""
    MODELS = [
        {"id": "mobilenet_v2_edge", "classes": ["person", "car", "truck", "dog", "cat"], "latency_ms": (10, 30)},
        {"id": "yolo_nas_edge", "classes": ["person", "car", "truck", "bicycle", "motorcycle", "bus"], "latency_ms": (20, 50)},
    ]

    @classmethod
    def infer(cls, image_data: str, model_id: Optional[str] = None) -> Dict[str, Any]:
        model = next((m for m in cls.MODELS if m["id"] == model_id), cls.MODELS[0])
        low, high = model["latency_ms"]
        latency = random.uniform(low, high)
        time.sleep(latency / 1000.0)

        # Generate 0-3 random detections
        num_detections = random.randint(0, 3)
        boxes = []
        for _ in range(num_detections):
            cls_name = random.choice(model["classes"])
            confidence = round(random.uniform(0.5, 0.99), 2)
            w = random.randint(40, 200)
            h = random.randint(40, 200)
            x = random.randint(0, max(1, 640 - w))
            y = random.randint(0, max(1, 480 - h))
            boxes.append({
                "x": x, "y": y, "w": w, "h": h,
                "label": cls_name, "confidence": confidence
            })

        return {
            "model_id": model["id"],
            "inference_time_ms": round(latency, 1),
            "boxes": boxes,
            "image_width": 640,
            "image_height": 480,
        }


class InferenceServer:
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=32)
        self._running = False

    def get_tools(self) -> Dict[str, Any]:
        return {
            "list_models": {
                "description": "List available inference models",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "run_inference": {
                "description": "Run TPU inference on an image",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image_data": {"type": "string", "description": "Base64-encoded image"},
                        "model_id": {"type": "string", "description": "Optional model ID"}
                    },
                    "required": ["image_data"],
                },
            },
            "batch_inference": {
                "description": "Run inference on multiple images",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "requests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "image_data": {"type": "string"},
                                    "model_id": {"type": "string"}
                                },
                                "required": ["image_data"]
                            }
                        }
                    },
                    "required": ["requests"],
                },
            },
        }

    async def handle_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "list_models":
            return await self._list_models()
        elif name == "run_inference":
            return await self._run_inference(arguments)
        elif name == "batch_inference":
            return await self._batch_inference(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def _list_models(self) -> list:
        return MockTPUInference.MODELS

    async def _run_inference(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        image_data = arguments.get("image_data", "")
        model_id = arguments.get("model_id")
        if not image_data:
            raise ValueError("image_data is required")
        # Validate base64 length (max ~10MB)
        if len(image_data) > 14_000_000:
            raise ValueError("image_data exceeds 10MB limit")
        return MockTPUInference.infer(image_data, model_id)

    async def _batch_inference(self, arguments: Dict[str, Any]) -> list:
        requests = arguments.get("requests", [])
        if not requests:
            raise ValueError("requests array is required")
        if len(requests) > 16:
            raise ValueError("batch size exceeds 16")
        results = []
        for req in requests:
            results.append(await self._run_inference(req))
        return results
