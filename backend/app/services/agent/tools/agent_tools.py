"""Tool implementations for code audit agent.

Upgraded:
- _safe_path: fixed prefix-boundary bypass (C:\\proj would match C:\\projects\\evil).
- read_file: size-aware (small files full read, large files head read) and
  marks files as covered via a callback.
- New tools: run_semgrep_scan / run_sca_scan / load_skill / verify_poc /
  mark_file_covered (explicit) — matching AutoCVE-style Scan/Triage/Verification.
"""

import os
import re
import json
from typing import Callable, Optional

from app.core.config import settings
from app.services.agent.scanners import engine as scan_engine
from app.services.agent.rules import loader as rules_loader
from app.services.agent.verification import sandbox as poc_sandbox


# Extensions that are never worth reading into context (generated/minified/lock)
SKIP_EXTENSIONS = {
    ".min.js", ".min.css", ".map", ".lock", ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".exe", ".class", ".jar", ".war", ".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg",
    ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".sqlite",
    ".db", ".bin", ".o", ".a", ".obj",
}
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", "vendor", "target", "coverage", ".idea", ".vscode",
}

SMALL_FILE_LINES = 400        # files with <= this many lines are read in full
LARGE_FILE_LINES = 250        # head excerpt lines for large files


class CodeAuditTools:
    """All tools available to the code audit agent"""

    def __init__(self, project_root: str, on_cover: Optional[Callable[[str], None]] = None):
        self.project_root = os.path.abspath(project_root)
        self.tool_result_budget = settings.TOOL_RESULT_BUDGET
        self._on_cover = on_cover  # called with relative path when a file is read
        self._rules = None

    # ── path safety ──────────────────────────────────────────────────────
    def _safe_path(self, path: str) -> str:
        """Prevent path traversal outside project root (boundary-aware)."""
        full = os.path.join(self.project_root, path)
        real = os.path.realpath(full)
        root = os.path.realpath(self.project_root)
        if real != root and not real.startswith(root + os.sep):
            raise ValueError(f"Path traversal blocked: {path}")
        return real

    @staticmethod
    def _is_skippable(rel_path: str) -> bool:
        parts = rel_path.replace("\\", "/").split("/")
        if any(d in SKIP_DIRS for d in parts):
            return True
        lower = rel_path.lower()
        return any(lower.endswith(ext) for ext in SKIP_EXTENSIONS)

    def _truncate(self, content: str, limit: Optional[int] = None) -> str:
        limit = limit or self.tool_result_budget
        if len(content) > limit:
            return content[:limit] + f"\n... [truncated at {limit} chars, total {len(content)}]"
        return content

    # ── core read/list tools ─────────────────────────────────────────────
    async def read_file(self, path: str, head_only: bool = False) -> str:
        """Read a file from the project (size-aware; large files return a head excerpt)."""
        try:
            full_path = self._safe_path(path)
            if not os.path.isfile(full_path):
                return json.dumps({"error": f"File not found: {path}"})
            if self._is_skippable(path):
                return json.dumps({"error": f"Skipped generated/binary file: {path}", "skipped": True})

            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            line_count = content.count("\n") + 1

            if self._on_cover:
                self._on_cover(path.replace("\\", "/"))

            excerpt = False
            if head_only:
                # Explicit head-only request: return head excerpt
                excerpt = True
                content = "\n".join(content.splitlines()[:SMALL_FILE_LINES])
            elif line_count > LARGE_FILE_LINES:
                # Large file: return head excerpt + guidance to grep specific parts
                excerpt = True
                content = "\n".join(content.splitlines()[:SMALL_FILE_LINES])

            payload = {
                "path": path,
                "content": self._truncate(content),
                "lines": line_count,
                "excerpt": excerpt,
            }
            if excerpt:
                payload["note"] = f"File has {line_count} lines; showing first {SMALL_FILE_LINES}. Use grep to locate specific patterns."
            return json.dumps(payload)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def read_file_range(self, path: str, start_line: int = 1, end_line: int = 200) -> str:
        """Read a specific line range of a file (for large-file deep dives)."""
        try:
            full_path = self._safe_path(path)
            if not os.path.isfile(full_path):
                return json.dumps({"error": f"File not found: {path}"})
            start_line = max(1, int(start_line))
            end_line = max(start_line, int(end_line))
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            excerpt = "".join(lines[start_line - 1:end_line])
            if self._on_cover:
                self._on_cover(path.replace("\\", "/"))
            return json.dumps({
                "path": path,
                "start_line": start_line,
                "end_line": min(end_line, len(lines)),
                "content": self._truncate(excerpt),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def list_files(self, pattern: str = "**/*") -> str:
        """List files matching a glob pattern (skips generated dirs)."""
        try:
            import fnmatch
            results = []
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    rel = os.path.relpath(os.path.join(root, f), self.project_root)
                    rel = rel.replace("\\", "/")
                    if self._is_skippable(rel):
                        continue
                    if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(f, pattern):
                        results.append(rel)
            results = results[:200]
            return json.dumps({"files": results, "count": len(results)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def grep(self, pattern: str, path: str = ".", context: int = 3) -> str:
        """Search for a pattern in project files using regex."""
        try:
            full_path = self._safe_path(path)
            try:
                result = subprocess_run(
                    ["rg", pattern, full_path, "--json", "-C", str(context),
                     "--max-filesize", "1M", "--glob", "!node_modules", "--glob", "!.git"],
                    timeout=30, cwd=self.project_root,
                )
                if result.returncode == 0 and result.stdout:
                    matches = []
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            try:
                                obj = json.loads(line)
                                if obj.get("type") == "match":
                                    data = obj.get("data", {})
                                    matches.append({
                                        "path": data.get("path", {}).get("text", ""),
                                        "line": data.get("line_number", 0),
                                        "content": (data.get("lines", {}).get("text", "").strip())[:300],
                                    })
                            except json.JSONDecodeError:
                                continue
                    payload = {"matches": matches[:50], "count": len(matches)}
                    data = json.dumps(payload, ensure_ascii=False)
                    if len(data) > self.tool_result_budget:
                        kept, size = [], 0
                        for m in matches:
                            item = json.dumps(m, ensure_ascii=False)
                            if size + len(item) > self.tool_result_budget * 0.8:
                                break
                            kept.append(m)
                            size += len(item)
                        payload = {"matches": kept, "count": len(matches), "truncated": True}
                        data = json.dumps(payload, ensure_ascii=False)
                    return data
                else:
                    # rg ran but no matches (or error) — fall through to python fallback? No: rg is authoritative when it ran.
                    return json.dumps({"matches": [], "count": 0})
            except FileNotFoundError:
                pass

            # Fallback: Python regex search
            matches = []
            regex = re.compile(pattern)
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, self.project_root).replace("\\", "/")
                    if self._is_skippable(rel):
                        continue
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append({"path": rel, "line": i, "content": line.strip()[:300]})
                                    if len(matches) >= 50:
                                        break
                    except Exception:
                        continue
                    if len(matches) >= 50:
                        break
            # Truncate INSIDE the JSON (never truncate the serialized string)
            payload = {"matches": matches, "count": len(matches)}
            data = json.dumps(payload, ensure_ascii=False)
            if len(data) > self.tool_result_budget:
                # keep matches until budget, then summarize
                kept, size = [], 0
                for m in matches:
                    item = json.dumps(m, ensure_ascii=False)
                    if size + len(item) > self.tool_result_budget * 0.8:
                        break
                    kept.append(m)
                    size += len(item)
                payload = {"matches": kept, "count": len(matches), "truncated": True}
                data = json.dumps(payload, ensure_ascii=False)
            return data
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def get_project_structure(self) -> str:
        """Get the project directory tree (first 3 levels)."""
        try:
            tree = []
            for root, dirs, files in os.walk(self.project_root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                level = root.replace(self.project_root, "").count(os.sep)
                indent = "  " * level
                basename = os.path.basename(root) or "."
                tree.append(f"{indent}{basename}/")
                if level < 3:
                    subindent = "  " * (level + 1)
                    for f in sorted(files)[:20]:
                        tree.append(f"{subindent}{f}")
            return self._truncate("\n".join(tree[:300]))
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ── engine scan tools (AutoCVE Scan/Triage) ──────────────────────────
    async def run_semgrep_scan(self) -> str:
        """Run Semgrep SAST scan over the project. Returns candidate findings for triage."""
        result = scan_engine.run_semgrep(self.project_root)
        return json.dumps({
            "skipped": result["skipped"],
            "reason": result.get("reason", ""),
            "error": result.get("error", ""),
            "candidates": [c.to_dict() for c in result["candidates"]][:settings.MAX_SCAN_CANDIDATES],
        }, ensure_ascii=False)

    async def run_sca_scan(self) -> str:
        """Run dependency (SCA) scan: pip-audit / npm audit. Returns known-vuln deps."""
        result = scan_engine.run_sca(self.project_root)
        return json.dumps({
            "skipped": result["skipped"],
            "reason": result.get("reason", ""),
            "error": result.get("error", ""),
            "candidates": [c.to_dict() for c in result["candidates"]][:settings.MAX_SCAN_CANDIDATES],
        }, ensure_ascii=False)

    async def run_custom_rules(self) -> str:
        """Run custom YAML rules (rule-as-code) over the project."""
        if self._rules is None:
            self._rules = rules_loader.discover_rules()
        hits = []
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                rel = os.path.relpath(os.path.join(root, fname), self.project_root).replace("\\", "/")
                if self._is_skippable(rel):
                    continue
                try:
                    with open(os.path.join(root, fname), "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue
                hits.extend(rules_loader.apply_custom_rules(content, rel, self._rules))
        return json.dumps({"rules_loaded": len(self._rules), "hits": hits[:settings.MAX_SCAN_CANDIDATES]}, ensure_ascii=False)

    # ── skill / verification tools ───────────────────────────────────────
    async def load_skill(self, skill_name: str) -> str:
        """Load the full content of a skill pack (on-demand deep knowledge)."""
        from ..skills.manager import SkillManager
        mgr = SkillManager()
        full = mgr.get_full_skill(skill_name)
        if full is None:
            return json.dumps({"error": f"Skill not found: {skill_name}", "available": mgr.list_skills()})
        return json.dumps({"skill": skill_name, "content": self._truncate(full, 6000)}, ensure_ascii=False)

    async def verify_poc(self, poc: str, description: str = "") -> str:
        """Static-validate (or sandbox-execute if enabled) a PoC for a finding."""
        result = poc_sandbox.verify_poc(poc)
        return json.dumps({
            "verified": result["verified"],
            "mode": result["mode"],
            "error": result["error"],
            "output": result["output"][:1000],
            "note": "PoC must be pure-Python stdlib; sandbox disabled => syntax check only." if result["mode"] == "static" else "",
        }, ensure_ascii=False)

    # ── coverage / finalize ──────────────────────────────────────────────
    async def mark_file_covered(self, file_path: str) -> str:
        """Explicitly mark a file as audited (even if no vulnerability found)."""
        if self._on_cover:
            self._on_cover(file_path.replace("\\", "/"))
        return json.dumps({"status": "ok", "file": file_path})

    async def finalize_finding(
        self,
        vulnerability_type: str,
        severity: str,
        title: str,
        file_path: str,
        source: str,
        sink: str,
        exploit_chain: str,
        confidence: str = "MEDIUM",
        line_start: int = 0,
        line_end: int = 0,
        code_snippet: str = "",
        description: str = "",
        poc: str = "",
        suggestion: str = "",
        cwe: str = "",
    ) -> str:
        """Submit a confirmed vulnerability finding."""
        required = {
            "vulnerability_type": vulnerability_type,
            "severity": severity,
            "title": title,
            "file_path": file_path,
            "source": source,
            "sink": sink,
            "exploit_chain": exploit_chain,
        }
        missing = [k for k, v in required.items() if not v or not str(v).strip()]
        if missing:
            return json.dumps({
                "status": "rejected",
                "reason": "missing_required_fields",
                "missing": missing,
                "message": f"FinalizeFinding rejected. Missing required fields: {', '.join(missing)}."
            })

        valid_types = {
            "SQL_Injection", "XSS", "SSRF", "Path_Traversal", "Deserialization",
            "Authentication_Bypass", "Authorization_Failure", "RCE", "XXE",
            "Open_Redirect", "Race_Condition", "Business_Logic", "Info_Disclosure",
            "Hardcoded_Secret", "Known_Vulnerable_Dependency", "Crypto_Issue",
        }
        if vulnerability_type not in valid_types:
            return json.dumps({
                "status": "rejected",
                "reason": "invalid_vulnerability_type",
                "message": f"Invalid type. Valid types: {', '.join(sorted(valid_types))}"
            })

        valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        if severity not in valid_severities:
            return json.dumps({
                "status": "rejected",
                "reason": "invalid_severity",
                "message": f"Invalid severity. Valid: {', '.join(sorted(valid_severities))}"
            })

        # Auto-fill CWE if not provided
        if not cwe:
            from app.services.agent.export.sarif import cwe_for_type
            cwe = cwe_for_type(vulnerability_type)

        # Auto-verify PoC if provided (static check always; sandbox if enabled)
        poc_status = {"verified": False, "mode": "none"}
        if poc and poc.strip():
            poc_status = poc_sandbox.verify_poc(poc)

        return json.dumps({
            "status": "accepted",
            "message": f"Finding accepted: {title}",
            "finding": {
                "vulnerability_type": vulnerability_type,
                "severity": severity,
                "title": title,
                "file_path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "code_snippet": code_snippet,
                "description": description,
                "source": source,
                "sink": sink,
                "exploit_chain": exploit_chain,
                "poc": poc,
                "suggestion": suggestion,
                "confidence": confidence,
                "cwe": cwe,
                "poc_verified": poc_status["verified"] if poc and poc.strip() else None,
            }
        })


def subprocess_run(cmd, timeout, cwd):
    import subprocess
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, errors="replace")
