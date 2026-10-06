import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


_ROOT = Path(__file__).resolve().parent


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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _local_config() -> dict[str, object]:
    path = _ROOT / "config" / "local.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if not key.startswith("_")}


def _local_str(settings: dict[str, object], name: str) -> str | None:
    value = settings.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _local_float(settings: dict[str, object], name: str) -> float | None:
    value = settings.get(name)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


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


AiProviderName = Literal["openai", "ollama", "none"]


@dataclass(frozen=True)
class AIProviderConfig:
    provider: AiProviderName
    provider_source: Literal["local_config", "environment", "fallback"]
    openai_model: str
    ollama_url: str
    ollama_model: str
    timeout_seconds: float

    @property
    def model_name(self) -> str | None:
        if self.provider == "openai":
            return self.openai_model
        if self.provider == "ollama":
            return self.ollama_model
        return None


CONFIG = ShahCadConfig()


# Values a user may leave in .env after copying the example. Treated as absent
# so the app reports "not configured" instead of claiming AI is available and
# then failing on the first request with an auth error.
_PLACEHOLDER_KEYS = {
    "",
    "your_api_key_here",
    "your-api-key-here",
    "changeme",
    "none",
    "null",
    "todo",
}


def openai_key_configured() -> bool:
    """True when a usable OPENAI_API_KEY is set.

    Loads `.env` first so this agrees with `ai.parser`, which does the same
    before building a client. Blank and placeholder values count as absent.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    value = (os.getenv("OPENAI_API_KEY") or "").strip()
    return value.lower() not in _PLACEHOLDER_KEYS


def ai_provider_config() -> AIProviderConfig:
    """Resolve AI provider settings without exposing secrets.

    Machine-local `config/local.json` wins over environment variables for
    non-secret provider settings. `OPENAI_API_KEY` is still read only from
    `.env`/the environment and never from local JSON.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    local = _local_config()
    provider_raw = _local_str(local, "ai_provider")
    provider_source: Literal["local_config", "environment", "fallback"] = "local_config"
    if provider_raw is None:
        provider_raw = os.getenv("SHAH_AI_PROVIDER")
        provider_source = "environment"
    if provider_raw is None:
        provider_raw = "openai" if openai_key_configured() else "none"
        provider_source = "fallback"

    provider = provider_raw.strip().lower()
    if provider in {"local", "local_ai"}:
        provider = "ollama"
    if provider in {"disabled", "manual", "off"}:
        provider = "none"
    if provider not in {"openai", "ollama", "none"}:
        provider = "none"

    openai_model = (
        _local_str(local, "openai_model")
        or os.getenv("OPENAI_MODEL")
        or "gpt-5-mini"
    )
    ollama_url = (
        _local_str(local, "ollama_url")
        or os.getenv("SHAH_OLLAMA_URL")
        or "http://127.0.0.1:11434"
    )
    ollama_model = (
        _local_str(local, "ollama_model")
        or os.getenv("SHAH_OLLAMA_MODEL")
        or "qwen2.5-coder:7b"
    )
    timeout = (
        _local_float(local, "ai_timeout_seconds")
        or _env_float("SHAH_AI_TIMEOUT_SECONDS", 120.0)
    )
    return AIProviderConfig(
        provider=provider,  # type: ignore[arg-type]
        provider_source=provider_source,
        openai_model=openai_model,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        timeout_seconds=max(1.0, timeout),
    )
