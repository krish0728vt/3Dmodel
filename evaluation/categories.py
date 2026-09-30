from __future__ import annotations

from enum import StrEnum


class BenchmarkCategory(StrEnum):
    BASIC_PRIMITIVES = "basic_primitives"
    MOUNTING_PARTS = "mounting_parts"
    ENCLOSURES = "enclosures"
    BRACKETS = "brackets"
    HOLES = "holes"
    PATTERNS = "patterns"
    BOOLEAN_OPERATIONS = "boolean_operations"
    SKETCHES = "sketches"
    LOFTS = "lofts"
    SWEEPS = "sweeps"
    SHELLS = "shells"
    PARAMETRICS = "parametrics"
    CONVERSATIONAL_EDITS = "conversational_edits"
    ENGINEERING_ANALYSIS = "engineering_analysis"
    ASSEMBLIES = "assemblies"
    CAPABILITIES = "capabilities"
    EXPORTS = "exports"
    INVALID_INPUTS = "invalid_inputs"
    AMBIGUOUS_INPUTS = "ambiguous_inputs"
