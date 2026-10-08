"""Resolve a friendly name or an id to a single device or scene."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar

from .errors import AmbiguousDeviceError, DeviceNotFoundError, SceneNotFoundError
from .models import Device, Scene


class _Named(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def name(self) -> str: ...


T = TypeVar("T", bound=_Named)


def resolve_device(query: str, devices: Sequence[Device]) -> Device:
    return _resolve(query, devices, "device", DeviceNotFoundError)


def resolve_scene(query: str, scenes: Sequence[Scene]) -> Scene:
    return _resolve(query, scenes, "scene", SceneNotFoundError)


def _resolve(query: str, items: Sequence[T], kind: str, not_found: type[Exception]) -> T:
    """Match an exact id, else an exact name ignoring case. Never guesses."""
    wanted = query.strip()
    for item in items:
        if item.id == wanted:
            return item

    matches = [item for item in items if item.name.casefold() == wanted.casefold()]
    if len(matches) == 1:
        return matches[0]
    if matches:
        candidates = ", ".join(f"{m.name!r} (id {m.id})" for m in matches)
        raise AmbiguousDeviceError(
            f"Several {kind}s are named {query!r}: {candidates}. "
            "Use the id instead. Nothing was sent."
        )

    available = ", ".join(repr(item.name) for item in items) or "none"
    raise not_found(f"No {kind} named {query!r}. Available {kind}s: {available}.")
