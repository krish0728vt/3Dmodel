from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ShahCadConfig:
    max_repair_attempts: int = _env_int("SHAH_MAX_REPAIR_ATTEMPTS", 2)
    learning_enabled: bool = _env_bool("SHAH_LEARNING_ENABLED", True)
    record_successful_patterns: bool = _env_bool("SHAH_RECORD_SUCCESSFUL_PATTERNS", True)
    capabilities_enabled: bool = _env_bool("SHAH_CAPABILITIES_ENABLED", True)
    capability_connect_timeout_seconds: int = _env_int("CAPABILITY_CONNECT_TIMEOUT", 5)
    capability_call_timeout_seconds: int = _env_int("CAPABILITY_CALL_TIMEOUT", 20)
    lesson_validated_successes: int = _env_int("SHAH_LESSON_VALIDATED_SUCCESSES", 3)
    lesson_trusted_successes: int = _env_int("SHAH_LESSON_TRUSTED_SUCCESSES", 8)
    lesson_deprecate_contradictions: int = _env_int("SHAH_LESSON_DEPRECATE_CONTRADICTIONS", 4)
    planning_context_max_lessons: int = _env_int("SHAH_PLANNING_MAX_LESSONS", 5)
    planning_context_max_patterns: int = _env_int("SHAH_PLANNING_MAX_PATTERNS", 3)
    planning_context_max_repair_strategies: int = _env_int("SHAH_PLANNING_MAX_REPAIR_STRATEGIES", 3)
    learning_db_path: Path = Path(os.getenv("SHAH_LEARNING_DB_PATH", "data/shah_learning.db"))
    capability_registry_path: Path = Path(
        os.getenv("SHAH_CAPABILITY_REGISTRY_PATH", "data/capabilities.json")
    )
    mcp_servers_config_path: Path = Path(os.getenv("SHAH_MCP_SERVERS_CONFIG", "config/mcp_servers.json"))
    default_printer_x_mm: int = _env_int("SHAH_DEFAULT_PRINTER_X_MM", 220)
    default_printer_y_mm: int = _env_int("SHAH_DEFAULT_PRINTER_Y_MM", 220)
    default_printer_z_mm: int = _env_int("SHAH_DEFAULT_PRINTER_Z_MM", 250)
    min_general_print_wall_mm: float = float(os.getenv("SHAH_MIN_GENERAL_PRINT_WALL_MM", "1.0"))
    small_print_hole_mm: float = float(os.getenv("SHAH_SMALL_PRINT_HOLE_MM", "2.0"))
    cnc_deep_hole_ratio: float = float(os.getenv("SHAH_CNC_DEEP_HOLE_RATIO", "10.0"))
    min_cnc_feature_mm: float = float(os.getenv("SHAH_MIN_CNC_FEATURE_MM", "0.8"))


CONFIG = ShahCadConfig()
