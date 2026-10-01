"""Typed models for deployment checks, process state, and local configuration."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class CheckResult(BaseModel):
    """One diagnostic outcome, reported by `doctor` and `setup`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: CheckStatus
    detail: str
    remedy: str | None = None

    @property
    def is_blocking(self) -> bool:
        return self.status is CheckStatus.FAIL


class DoctorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_version: str
    build: str | None = None
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if r.status is CheckStatus.FAIL]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.status is CheckStatus.WARN]

    @property
    def overall(self) -> str:
        if self.failures:
            return "NOT READY"
        if self.warnings:
            return "READY WITH WARNINGS"
        return "READY"

    @property
    def exit_code(self) -> int:
        """Warnings alone are not a failure, so scripted callers can gate on this."""
        return 1 if self.failures else 0


class LaunchMode(str, Enum):
    DEV = "dev"
    PRODUCTION = "production"


class ProcessRecord(BaseModel):
    """A child process the launcher started, as persisted to the state file."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["backend", "frontend"]
    pid: int
    port: int
    command: list[str] = Field(default_factory=list)
    log_path: str | None = None


class LaunchState(BaseModel):
    """Contents of `runtime/shah_processes.json`.

    Only processes recorded here are ever eligible to be stopped, and each PID is
    re-validated before use so a stale file cannot target an unrelated process.
    """

    model_config = ConfigDict(extra="forbid")

    app_version: str
    mode: LaunchMode
    host: str
    started_at: str
    launcher_pid: int
    processes: list[ProcessRecord] = Field(default_factory=list)

    def process(self, name: str) -> ProcessRecord | None:
        for record in self.processes:
            if record.name == name:
                return record
        return None


class LocalConfig(BaseModel):
    """Optional `config/local.json`. Machine-specific settings only, never secrets."""

    model_config = ConfigDict(extra="forbid")

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_port: int = 5173
    open_browser: bool = True
    startup_timeout: int = 30
    mode: LaunchMode = LaunchMode.PRODUCTION
