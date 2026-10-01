from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

from deployment_safety import scan as scan_deployment_safety


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".venv311",
    "__pycache__",
    "data",
    "htmlcov",
    "node_modules",
    "outputs",
    "test-results",
    "venv",
    "web/dist",
    "web/node_modules",
}
CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
FRONTEND_SECRET_DIRS = {ROOT / "web" / "src", ROOT / "web" / "public"}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]
# The frontend must never carry a secret. A bare mention of a variable name in
# user-facing help text is legitimate and required ("Configure OPENAI_API_KEY in
# .env"), so these patterns match the shapes that would actually embed or read a
# secret in the bundle, not any occurrence of the word.
FRONTEND_SECRET_PATTERNS = [
    (
        re.compile(r"OPENAI_API_KEY\s*[=:]\s*['\"`]?\S"),
        "assigns a value to OPENAI_API_KEY",
    ),
    (
        re.compile(r"(?:process|import\.meta)\.env\.[A-Za-z_]*(?:API_KEY|SECRET|TOKEN|PASSWORD)"),
        "reads a secret from the build environment",
    ),
    (
        re.compile(r"""Authorization\s*:\s*['\"`]\s*(?:Bearer|Basic)\s+\S"""),
        "hardcodes an Authorization header value",
    ),
]
SECRET_FILE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore", ".jks")
SECRET_FILE_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".npmrc", ".pypirc"}


def main() -> int:
    findings: list[str] = []
    for path in _iter_files():
        if path.suffix == ".py":
            findings.extend(_scan_python_ast(path))
        if path.suffix in CODE_SUFFIXES:
            findings.extend(_scan_text_code(path))
        if _is_frontend_file(path):
            findings.extend(_scan_frontend_secrets(path))
    findings.extend(_check_env_ignored())
    findings.extend(_check_tracked_secret_files())
    findings.extend(scan_deployment_safety())
    if findings:
        print("Security check failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Security check passed.")
    return 0


def _check_env_ignored() -> list[str]:
    """`.env` must stay ignored so real keys cannot be committed by accident."""
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        return ["missing .gitignore, so .env is not guaranteed to be ignored"]
    entries = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    if not entries & {".env", ".env*", "*.env", "/.env"}:
        return [".gitignore does not ignore .env"]
    return []


def _check_tracked_secret_files() -> list[str]:
    """Flag credential-bearing files that git is actually tracking."""
    tracked = _tracked_files()
    if tracked is None:
        return []
    findings: list[str] = []
    for relative in tracked:
        name = relative.rsplit("/", 1)[-1]
        if name == ".env" or (name.startswith(".env.") and not name.endswith(".example")):
            findings.append(f"{relative} is tracked by git but may contain secrets")
            continue
        if any(name.endswith(suffix) for suffix in SECRET_FILE_SUFFIXES) or name in SECRET_FILE_NAMES:
            findings.append(f"{relative} looks like a committed credential file")
    return findings


def _tracked_files() -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(relative == skip or relative.startswith(f"{skip}/") for skip in SKIP_DIRS):
            continue
        if path.suffix in CODE_SUFFIXES or _is_frontend_file(path):
            files.append(path)
    return files


def _scan_python_ast(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except UnicodeDecodeError:
        return [f"{_rel(path)} is not valid UTF-8"]
    except SyntaxError as exc:
        return [f"{_rel(path)} has syntax error: {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"eval", "exec"}:
                findings.append(f"{_rel(path)}:{node.lineno} uses {name}()")
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    findings.append(f"{_rel(path)}:{node.lineno} passes shell=True")
    return findings


def _scan_text_code(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"{_rel(path)} contains a private-key or token-like pattern")
    return findings


def _scan_frontend_secrets(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings
    for pattern, description in FRONTEND_SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            line = text[: match.start()].count("\n") + 1
            findings.append(f"{_rel(path)}:{line} {description}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"{_rel(path)} contains frontend private-key or token-like pattern")
    return findings


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_frontend_file(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT / "web" / "src")
        return True
    except ValueError:
        pass
    try:
        path.resolve().relative_to(ROOT / "web" / "public")
        return True
    except ValueError:
        return False


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
