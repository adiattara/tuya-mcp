"""Typed views over Tuya API payloads."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    category: str
    online: bool

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Device:
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name") or payload["id"]),
            category=str(payload.get("category") or "unknown"),
            online=bool(payload.get("online", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Scene:
    """A tap-to-run scene of the linked app account."""

    id: str
    name: str
    enabled: bool
    home: str

    @classmethod
    def from_api(cls, payload: dict[str, Any], home: str) -> Scene:
        return cls(
            id=str(payload["id"]),
            name=str(payload.get("name") or payload["id"]),
            enabled=payload.get("status") != "disable",
            home=home,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataPoint:
    """One data point (DP) of a device: its code, type and allowed values."""

    code: str
    type: str
    values: dict[str, Any]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> DataPoint:
        return cls(
            code=str(payload["code"]),
            type=str(payload.get("type") or ""),
            values=_parse_json_object(payload.get("values")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "type": self.type, "values": self.values}


@dataclass(frozen=True)
class Specification:
    """What a device accepts (functions) and reports (status)."""

    category: str
    functions: dict[str, DataPoint] = field(default_factory=dict)
    status: dict[str, DataPoint] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Specification:
        return cls(
            category=str(payload.get("category") or "unknown"),
            functions=_index(payload.get("functions")),
            status=_index(payload.get("status")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "functions": [dp.to_dict() for dp in self.functions.values()],
            "status": [dp.to_dict() for dp in self.status.values()],
        }


def _index(items: Any) -> dict[str, DataPoint]:
    points = (DataPoint.from_api(item) for item in items or [] if "code" in item)
    return {dp.code: dp for dp in points}


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
