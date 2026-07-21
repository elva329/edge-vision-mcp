#!/usr/bin/env python3
"""
Rule MCP Server
- Zone crossing, loitering, object left behind rules
- Alert generation and acknowledgement
"""
import asyncio
import time
import uuid
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("rule-server")

@dataclass
class Alert:
    alert_id: str
    camera_id: str
    rule_name: str
    timestamp: str
    details: Dict[str, Any]
    acknowledged: bool = False


@dataclass
class Rule:
    rule_id: str
    name: str
    camera_id: str
    config: Dict[str, Any]
    active: bool = True


class RuleEngine:
    def __init__(self):
        self.rules: Dict[str, Rule] = {}
        self.alerts: List[Alert] = []
        self._state: Dict[str, Any] = {}  # camera_id -> state

    def get_tools(self) -> Dict[str, Any]:
        return {
            "define_rule": {
                "description": "Create or update a rule",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "rule_spec": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Rule name"},
                                "camera_id": {"type": "string", "description": "Camera ID"},
                                "type": {"type": "string", "enum": ["zone_crossing", "loitering", "object_left"]},
                                "zone": {"type": "array", "description": "Polygon points [[x,y],...]"},
                                "threshold_seconds": {"type": "number", "description": "Loitering threshold"},
                            },
                            "required": ["name", "camera_id", "type"],
                        }
                    },
                    "required": ["rule_spec"],
                },
            },
            "list_rules": {
                "description": "List active rules",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            "evaluate": {
                "description": "Evaluate inference results against rules",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID"},
                        "inference_results": {"type": "object", "description": "Inference result object"},
                    },
                    "required": ["camera_id", "inference_results"],
                },
            },
            "acknowledge_alert": {
                "description": "Acknowledge an alert",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "alert_id": {"type": "string", "description": "Alert ID"}
                    },
                    "required": ["alert_id"],
                },
            },
            "record_clip": {
                "description": "Record a clip (mock)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "camera_id": {"type": "string", "description": "Camera ID"},
                        "duration": {"type": "number", "description": "Duration in seconds"},
                    },
                    "required": ["camera_id", "duration"],
                },
            },
        }

    async def handle_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "define_rule":
            return await self._define_rule(arguments["rule_spec"])
        elif name == "list_rules":
            return await self._list_rules()
        elif name == "evaluate":
            return await self._evaluate(arguments["camera_id"], arguments["inference_results"])
        elif name == "acknowledge_alert":
            return await self._acknowledge_alert(arguments["alert_id"])
        elif name == "record_clip":
            return await self._record_clip(arguments["camera_id"], arguments["duration"])
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def _define_rule(self, rule_spec: Dict[str, Any]) -> Dict[str, Any]:
        rule_id = str(uuid.uuid4())
        rule = Rule(
            rule_id=rule_id,
            name=rule_spec["name"],
            camera_id=rule_spec["camera_id"],
            config=rule_spec,
        )
        self.rules[rule_id] = rule
        logger.info(f"Rule defined: {rule.name} ({rule_id})")
        return {"rule_id": rule_id, "name": rule.name, "status": "created"}

    async def _list_rules(self) -> list:
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "camera_id": r.camera_id,
                "type": r.config.get("type"),
                "active": r.active,
            }
            for r in self.rules.values()
        ]

    async def _evaluate(self, camera_id: str, inference_results: Dict[str, Any]) -> list:
        boxes = inference_results.get("boxes", [])
        alerts = []
        for rule in self.rules.values():
            if rule.camera_id != camera_id or not rule.active:
                continue
            triggered = self._check_rule(rule, boxes)
            if triggered:
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    camera_id=camera_id,
                    rule_name=rule.name,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    details={"rule_type": rule.config.get("type"), "boxes": boxes},
                )
                self.alerts.append(alert)
                alerts.append({
                    "alert_id": alert.alert_id,
                    "rule_name": alert.rule_name,
                    "timestamp": alert.timestamp,
                    "camera_id": alert.camera_id,
                })
        return alerts

    def _check_rule(self, rule: Rule, boxes: List[Dict[str, Any]]) -> bool:
        rule_type = rule.config.get("type")
        if rule_type == "zone_crossing":
            zone = rule.config.get("zone", [])
            if not zone:
                return False
            # Simplified: check if any box center is inside polygon (AABB for mock)
            min_x = min(p[0] for p in zone)
            max_x = max(p[0] for p in zone)
            min_y = min(p[1] for p in zone)
            max_y = max(p[1] for p in zone)
            for box in boxes:
                cx = box["x"] + box["w"] / 2
                cy = box["y"] + box["h"] / 2
                if min_x <= cx <= max_x and min_y <= cy <= max_y:
                    return True
        elif rule_type == "loitering":
            # Mock: always return False (no temporal tracking in Phase 1)
            return False
        elif rule_type == "object_left":
            # Mock: trigger if box labeled as 'person' exists
            return any(b.get("label") == "person" for b in boxes)
        return False

    async def _acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return {"alert_id": alert_id, "status": "acknowledged"}
        raise ValueError(f"Alert not found: {alert_id}")

    async def _record_clip(self, camera_id: str, duration: float) -> Dict[str, Any]:
        clip_id = str(uuid.uuid4())
        return {"clip_id": clip_id, "camera_id": camera_id, "duration": duration, "status": "recording"}
