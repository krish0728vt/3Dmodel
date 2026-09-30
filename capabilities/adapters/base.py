from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from capabilities.models import CapabilityManifest


class ExternalCapabilityAdapter(ABC):
    """Generic interface for future external CAD capabilities."""

    @abstractmethod
    def get_metadata(self) -> CapabilityManifest:
        raise NotImplementedError

    @abstractmethod
    def list_tools(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_tool_schema(self, tool_name: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def validate_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def run_self_test(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
