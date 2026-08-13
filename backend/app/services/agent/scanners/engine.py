"""Scan engine base + Semgrep SAST scanner + SCA scanner.

All scanners gracefully degrade: if the underlying CLI is not installed,
they return an empty result with a `skipped` flag instead of crashing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import settings


@dataclass
class ScanCandidate:
    """A single engine-level hit that the LLM should confirm / triage."""
    engine: str                 # semgrep | sca | rule
    rule_id: str
    severity: str               # CRITICAL / HIGH / MEDIUM / LOW / ERROR
    file_path: str
    line_start: int = 0
    line_end: int = 0
    message: str = ""
    code: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "engine": self.engine,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "message": self.message,
            "code": self.code,
            "metadata": self.metadata,
        }


def _run_cli(cmd: List[str], timeout: int, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a CLI with a timeout; raise FileNotFoundError if binary missing."""
    proc = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        errors="replace",
    )
    return proc


# ──────────────────────────────────────────────────────────────────────────
# Semgrep SAST
# ──────────────────────────────────────────────────────────────────────────

def semgrep_available() -> bool:
    return shutil.which("semgrep") is not None


def _map_semgrep_severity(sev: str) -> str:
    sev = (sev or "WARNING").upper()
    return {"ERROR": "CRITICAL", "WARNING": "HIGH"}.get(sev, "MEDIUM")


def run_semgrep(project_root: str, config: Optional[str] = None) -> dict:
    """Run Semgrep over project_root. Returns {skipped, candidates, error}."""
    if not settings.SEMGREP_ENABLED:
        return {"skipped": True, "reason": "disabled", "candidates": [], "error": ""}
    if not semgrep_available():
        return {"skipped": True, "reason": "semgrep not installed", "candidates": [], "error": ""}

    cfg = config or settings.SEMGREP_CONFIG
    try:
        proc = _run_cli(
            ["semgrep", "scan", "--json", "--config", cfg, "--no-rewrite-rule-ids",
             "--quiet", "--timeout", "30", project_root],
            timeout=settings.SEMGREP_TIMEOUT,
        )
    except FileNotFoundError:
        return {"skipped": True, "reason": "semgrep not installed", "candidates": [], "error": ""}
    except subprocess.TimeoutExpired:
        return {"skipped": False, "reason": "timeout", "candidates": [], "error": "semgrep timeout"}

    candidates: List[ScanCandidate] = []
    try:
        data = json.loads(proc.stdout or "{}")
        for res in data.get("results", []):
            path = res.get("path", "")
            rel = os.path.relpath(path, project_root) if path else ""
            start = res.get("start", {}) or {}
            end = res.get("end", {}) or {}
            rule = res.get("check_id", "") or ""
            candidates.append(ScanCandidate(
                engine="semgrep",
                rule_id=rule,
                severity=_map_semgrep_severity(res.get("extra", {}).get("severity", "WARNING")),
                file_path=rel.replace("\\", "/"),
                line_start=int(start.get("line", 0) or 0),
                line_end=int(end.get("line", 0) or 0),
                message=res.get("extra", {}).get("message", ""),
                code=res.get("extra", {}).get("lines", ""),
            ))
    except Exception as e:  # noqa: BLE001
        return {"skipped": False, "reason": "parse_error", "candidates": [], "error": str(e)}

    return {"skipped": False, "reason": "", "candidates": candidates, "error": ""}


# ──────────────────────────────────────────────────────────────────────────
# SCA (dependency scanning) — osv-scanner / pip-audit / npm audit
# ──────────────────────────────────────────────────────────────────────────

def _sca_pip_audit(project_root: str) -> List[ScanCandidate]:
    req = os.path.join(project_root, "requirements.txt")
    if not os.path.isfile(req) or not shutil.which("pip-audit"):
        return []
    try:
        proc = _run_cli(["pip-audit", "-r", req, "--format", "json"], timeout=settings.SCA_TIMEOUT)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    out = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            out.append(ScanCandidate(
                engine="sca",
                rule_id="SCA-PIP",
                severity="HIGH",
                file_path="requirements.txt",
                message=f"{dep.get('name')} {dep.get('version')}: {vuln.get('id', '')} - {vuln.get('description', '')[:200]}",
                metadata={"package": dep.get("name"), "version": dep.get("version"), "cve": vuln.get("id", "")},
            ))
    return out


def _sca_npm_audit(project_root: str) -> List[ScanCandidate]:
    pkg = os.path.join(project_root, "package-lock.json")
    if not os.path.isfile(pkg) or not shutil.which("npm"):
        return []
    try:
        # shutil.which already resolves npm.cmd on Windows
        proc = _run_cli([shutil.which("npm"), "audit", "--json"], timeout=settings.SCA_TIMEOUT, cwd=project_root)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    out = []
    for adv in (data.get("advisories") or {}).values():
        out.append(ScanCandidate(
            engine="sca",
            rule_id="SCA-NPM",
            severity=adv.get("severity", "HIGH").upper(),
            file_path="package-lock.json",
            message=f"{adv.get('module_name', '')}: {adv.get('title', '')} [{adv.get('cves', [])}]",
            metadata={"package": adv.get("module_name"), "cve": ",".join(adv.get("cves", []))},
        ))
    return out


def run_sca(project_root: str) -> dict:
    """Run dependency scanners. Returns {skipped, candidates, error}."""
    if not settings.SCA_ENABLED:
        return {"skipped": True, "reason": "disabled", "candidates": [], "error": ""}

    candidates: List[ScanCandidate] = []
    candidates += _sca_pip_audit(project_root)
    candidates += _sca_npm_audit(project_root)

    if not candidates and not (shutil.which("pip-audit") or os.path.isfile(os.path.join(project_root, "package-lock.json"))):
        return {"skipped": True, "reason": "no dependency manifests / scanners", "candidates": [], "error": ""}

    return {"skipped": False, "reason": "", "candidates": candidates, "error": ""}


# ──────────────────────────────────────────────────────────────────────────
# Taint sink/source helper (lightweight guidance for the LLM)
# ──────────────────────────────────────────────────────────────────────────

SINK_PATTERNS = {
    "command_exec": ["exec(", "system(", "shell_exec(", "passthru(", "proc_open(", "popen(", "subprocess.run", "subprocess.Popen", "os.system", "Runtime.getRuntime().exec"],
    "sql": ["->query(", "->exec(", "->prepare(", "cursor.execute", "db.query", "sequelize.query", "mysqli_query", "mysql_query", "Statement.executeQuery", "createQuery", "\.raw("],
    "file_read": ["file_get_contents(", "readfile(", "fopen(", "include(", "require(", "importlib.import_module", "load_controller", "Files.readString", "new File("],
    "eval": ["eval(", "assert(", "eval(\"", "v8.compile", "Function("],
    "serialize": ["unserialize(", "pickle.loads", "ObjectInputStream", "yaml.load", "JSON.parseObject"],
    "ssrf": ["file_get_contents(", "requests.get(", "urllib.request", "HttpClient", "curl_exec", "fetch("],
    "upload": ["move_uploaded_file", "saveFile", "upload", "writeFile", "os.write"],
    "xxe": ["simplexml_load_string", "XMLReader", "DocumentBuilder", "libxml", "loadXML", "SAXParser"],
    "redirect": ["header(Location", "redirect(", "location.href", "res.redirect", "sendRedirect"],
}

SOURCE_PATTERNS = [
    "$_GET", "$_POST", "$_REQUEST", "$_FILES", "$_COOKIE", "request.args", "request.form",
    "request.json", "req.query", "req.params", "req.body", "ctx.query", "ctx.params",
    "HttpServletRequest", "@RequestParam", "@PathVariable", "@RequestBody", "getParameter",
    "input()", "os.environ", "sys.argv", "argv",
]


def find_sink_hits(content: str) -> list:
    """Return list of sink kinds matched in a file content string (for LLM guidance)."""
    hits = []
    lower = content.lower()
    for kind, patterns in SINK_PATTERNS.items():
        for p in patterns:
            if p.lower() in lower:
                hits.append({"kind": kind, "pattern": p})
                break
    return hits
