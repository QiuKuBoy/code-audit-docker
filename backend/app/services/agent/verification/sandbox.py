"""PoC verification sandbox (opt-in, heavily constrained).

Design goals (safety-first):
- Never executes arbitrary attacker-supplied commands.
- Only runs *generated* PoCs that are pure-Python scripts using the standard
  library, with a hard timeout, in an isolated temp working directory.
- Reads are limited to the temp dir; no network, no shell.
- If SANDBOX_ENABLED is False, verification is a static sanity check only
  (validate PoC syntax, never execute).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile

from app.core.config import settings

_ALLOWED_IMPORTS = {"json", "re", "hashlib", "base64", "urllib.parse", "datetime"}


def _validate_poc_syntax(poc: str) -> tuple:
    """Return (ok, error). AST parse + import allowlist."""
    if not poc or not poc.strip():
        return False, "empty poc"
    try:
        tree = ast.parse(poc)
    except SyntaxError as e:
        return False, f"syntax error: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.name or "").split(".")[0]
                if root not in _ALLOWED_IMPORTS:
                    return False, f"disallowed import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in _ALLOWED_IMPORTS:
                return False, f"disallowed import: {node.module}"
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in {"system", "popen", "run", "call", "check_output", "Popen", "exec", "eval", "__import__", "mro", "__subclasses__", "__globals__"}:
                return False, f"disallowed call: {fn.attr}"
            if isinstance(fn, ast.Name) and fn.id in {"exec", "eval", "open", "compile", "__import__", "getattr", "globals", "vars", "locals", "breakpoint", "exit", "quit", "input"}:
                return False, f"disallowed call: {fn.id}"
        elif isinstance(node, ast.Attribute):
            # Block dunder attribute *access* chains used for sandbox escapes
            if node.attr in {"__subclasses__", "__globals__", "__builtins__", "__import__", "__base__", "__bases__", "mro"}:
                return False, f"disallowed attribute access: {node.attr}"
    return True, ""


def verify_poc(poc: str, timeout: int = None) -> dict:
    """Verify a PoC. If sandbox disabled: static check only.

    Returns {verified, mode, error, output}.
    """
    timeout = timeout or settings.SANDBOX_TIMEOUT
    ok, err = _validate_poc_syntax(poc)
    if not ok:
        return {"verified": False, "mode": "static", "error": err, "output": ""}

    if not settings.SANDBOX_ENABLED:
        # Static check only — the PoC was NOT executed, so don't claim verified
        return {"verified": None, "mode": "static", "error": "", "output": "(sandbox disabled - syntax validated only)"}

    # Dynamic execution in isolated temp dir, no network, no shell
    with tempfile.TemporaryDirectory(prefix="codeaudit_poc_") as tmp:
        script = os.path.join(tmp, "poc.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write(poc)
        try:
            env = {
                "PATH": "", "HOME": tmp, "TMP": tmp, "TEMP": tmp,
                "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0",
            }
            proc = subprocess.run(
                [sys.executable, "-I", script],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmp, env=env, errors="replace",
            )
            out = (proc.stdout or "")[-settings.SANDBOX_MAX_OUTPUT:]
            if proc.returncode == 0:
                return {"verified": True, "mode": "sandbox", "error": "", "output": out}
            return {"verified": False, "mode": "sandbox", "error": (proc.stderr or "")[-2000:], "output": out}
        except subprocess.TimeoutExpired:
            return {"verified": False, "mode": "sandbox", "error": "timeout", "output": ""}
        except Exception as e:  # noqa: BLE001
            return {"verified": False, "mode": "sandbox", "error": str(e), "output": ""}
