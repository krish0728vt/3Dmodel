from __future__ import annotations

from capabilities.registry import CapabilityRegistry
from assemblies.store import AssemblyStore
from exports.store import ExportStore
from learning.store import LearningStore
from projects.store import ProjectStore


def get_project_store() -> ProjectStore:
    return ProjectStore()


def get_assembly_store() -> AssemblyStore:
    return AssemblyStore()


def get_export_store() -> ExportStore:
    return ExportStore()


def get_learning_store() -> LearningStore:
    return LearningStore()


def get_capability_registry() -> CapabilityRegistry:
    return CapabilityRegistry()
