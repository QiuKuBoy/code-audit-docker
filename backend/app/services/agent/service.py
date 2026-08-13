"""Audit Service - Orchestrates the full audit workflow (upgraded).

Changes vs original:
- Engine scans (semgrep / sca / custom rules) run synchronously BEFORE the ReAct
  loop starts; candidates are injected into the system prompt for Triage.
- Project file inventory is captured up-front for coverage-driven termination.
- MAX_TURNS is dynamically scaled by project size.
- New tools are registered: read_file_range, run_semgrep_scan, run_sca_scan,
  run_custom_rules, load_skill, verify_poc, mark_file_covered.
"""

import os
import uuid
import asyncio
import json
from datetime import timezone, datetime
from typing import Optional

from app.core.config import settings
from app.core.database import async_session
from app.models.models import Project, Audit, APIKey
from sqlalchemy import select

from ..llm.factory import LLMFactory
from ..llm.base_adapter import LLMAdapter
from .core.state import AgentState
from .core.memory import MemoryManager
from .core.registry import ToolRegistry
from .core.loop import ReActLoop
from .tools.agent_tools import CodeAuditTools
from .skills.manager import SkillManager
from .prompts.system_prompt import build_system_prompt
from .scanners import engine as scan_engine
from .rules import loader as rules_loader
from .verification import sandbox as poc_sandbox
from .tools.mcp_tools import get_mcp_bridge, init_mcp_bridge, load_merged_mcp_configs

import logging

logger = logging.getLogger(__name__)

# Strong references to background audit tasks (prevents premature GC)
_BACKGROUND_TASKS: set = set()


def detect_tech_stack(project_path: str) -> list:
    """Auto-detect project tech stack from files"""
    stack = []
    checks = {
        "requirements.txt": "Python",
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "package.json": "Node.js",
        "tsconfig.json": "TypeScript",
        "go.mod": "Go",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "Cargo.toml": "Rust",
        "composer.json": "PHP",
        "Gemfile": "Ruby",
        "csproj": "C#",
        "Dockerfile": "Docker",
    }
    for filename, tech in checks.items():
        if os.path.isfile(os.path.join(project_path, filename)):
            stack.append(tech)

    # Check for frameworks
    pkg_json = os.path.join(project_path, "package.json")
    if os.path.isfile(pkg_json):
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                import json as _json
                pkg = _json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react" in deps: stack.append("React")
                if "vue" in deps: stack.append("Vue")
                if "express" in deps: stack.append("Express")
                if "fastify" in deps: stack.append("Fastify")
                if "next" in deps: stack.append("Next.js")
                if "django" in deps: stack.append("Django")
                if "flask" in deps: stack.append("Flask")
        except Exception:
            pass

    if os.path.isfile(os.path.join(project_path, "manage.py")):
        if "Python" not in stack:
            stack.append("Python")
        stack.append("Django")

    if os.path.isfile(os.path.join(project_path, "app.py")) or os.path.isfile(os.path.join(project_path, "main.py")):
        if "Python" not in stack:
            stack.append("Python")

    return list(set(stack)) if stack else ["Unknown"]


def discover_project_files(project_root: str, limit: int = 500) -> list:
    """Inventory source files (excluding generated dirs) for coverage tracking."""
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
        ".next", ".nuxt", "vendor", "target", "coverage", ".idea", ".vscode",
    }
    skip_ext = {
        ".min.js", ".min.css", ".map", ".lock", ".pyc", ".so", ".dll", ".exe",
        ".class", ".jar", ".war", ".zip", ".gz", ".tar", ".png", ".jpg", ".jpeg",
        ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".pdf",
        ".sqlite", ".db", ".bin", ".o", ".a", ".obj",
    }
    files = []
    for root, dirs, fnames in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in fnames:
            rel = os.path.relpath(os.path.join(root, f), project_root).replace("\\", "/")
            lower = rel.lower()
            if any(lower.endswith(e) for e in skip_ext):
                continue
            if any(d in rel.split("/") for d in skip_dirs):
                continue
            files.append(rel)
            if len(files) >= limit:
                return files
    return files


def run_engine_scans(project_root: str, mode: str) -> dict:
    """Run all engine scans synchronously before the agent loop. Returns candidates."""
    candidates = []

    # Semgrep SAST
    semgrep = scan_engine.run_semgrep(project_root)
    if not semgrep.get("skipped"):
        candidates.extend(c.to_dict() for c in semgrep.get("candidates", []))
    elif semgrep.get("skipped"):
        candidates.extend([])

    # SCA (dependencies)
    sca = scan_engine.run_sca(project_root)
    if not sca.get("skipped"):
        candidates.extend(c.to_dict() for c in sca.get("candidates", []))

    # Custom rules (rule-as-code)
    rules = rules_loader.discover_rules()
    if rules:
        for root, dirs, fnames in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in {
                ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
                ".next", ".nuxt", "vendor", "target",
            }]
            for f in fnames:
                rel = os.path.relpath(os.path.join(root, f), project_root).replace("\\", "/")
                if any(rel.lower().endswith(e) for e in (".min.js", ".min.css", ".map", ".lock", ".png", ".jpg")):
                    continue
                try:
                    with open(os.path.join(root, f), "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                    candidates.extend(rules_loader.apply_custom_rules(content, rel, rules))
                except Exception:
                    continue

    # Dedupe by (engine, rule_id, file_path, line)
    seen = set()
    deduped = []
    for c in candidates:
        key = (c.get("engine"), c.get("rule_id"), c.get("file_path"), c.get("line_start", 0))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    cap = settings.MAX_SCAN_CANDIDATES_QUICK if mode == "quick" else settings.MAX_SCAN_CANDIDATES
    return {"candidates": deduped[:cap], "total_raw": len(candidates)}


async def _resolve_api_key(provider: str, explicit_key: str = "") -> str:
    """Resolve the API key from DB api_keys table (the only source of truth)."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    async with async_session() as db:
        result = await db.execute(
            select(APIKey)
            .where(APIKey.provider == provider.lower())
            .order_by(APIKey.updated_at.desc())
            .limit(1)
        )
        k = result.scalar_one_or_none()
        if k and k.api_key and k.api_key.strip():
            from app.core.crypto import decrypt_secret
            return decrypt_secret(k.api_key).strip()
    raise ValueError(
        f"No API key configured for provider '{provider}'. "
        f"Please go to Settings → API Keys and add one first."
    )


async def _verify_findings(findings: list, primary_llm, primary_provider: str = "") -> list:
    """Adversarial verification of findings before they are persisted.

    Uses FindingVerifier with a secondary model (different from primary) when available.
    REJECTED findings are dropped; others keep confidence, and the
    verifier's suggested fix is appended to the suggestion field.
    """
    from .core.specialists import FindingVerifier

    if not findings:
        return findings

    # Try to build a secondary adapter from available API keys (different provider)
    secondary = None
    try:
        from app.services.llm.factory import LLMFactory
        from app.core.database import async_session
        from app.models.models import APIKey
        from sqlalchemy import select

        async def _pick_secondary():
            async with async_session() as db:
                result = await db.execute(
                    select(APIKey)
                    .where(APIKey.provider != (primary_provider or "").lower())
                    .order_by(APIKey.updated_at.desc())
                )
                keys = result.scalars().all()
                for k in keys:
                    if k.api_key and k.api_key.strip():
                        try:
                            from app.core.crypto import decrypt_secret
                            decrypted = decrypt_secret(k.api_key).strip()
                            if decrypted:
                                return LLMFactory.create(
                                    provider=k.provider,
                                    api_key=decrypted,
                                    model=k.model or None,
                                    base_url=k.base_url or None,
                                )
                        except Exception:
                            continue
            return None

        secondary = await _pick_secondary()
    except Exception:
        secondary = None

    verifier = FindingVerifier(primary_llm, secondary or primary_llm)
    results = await verifier.verify_batch(findings)

    kept = []
    for r in results:
        if r.verdict == "REJECTED":
            continue  # false positive — drop
        f = r.finding
        # Merge verifier feedback into the finding
        if r.suggested_fix and not f.suggestion:
            f.suggestion = r.suggested_fix
        if r.confidence == "HIGH" and f.confidence == "MEDIUM":
            f.confidence = "HIGH"
        kept.append(f)
    return kept


async def create_project(name: str, path: str, description: str = "", language: str = "") -> dict:
    """Create a project record and detect tech stack.

    Args:
        language: optional manual override ("auto" or "" => auto-detect).
    """
    project_id = f"proj_{uuid.uuid4().hex[:12]}"

    if not os.path.isdir(path):
        raise ValueError(f"Project path does not exist: {path}")

    if language and language.lower() not in ("auto", ""):
        tech_stack = [language]
    else:
        tech_stack = detect_tech_stack(path)

    async with async_session() as db:
        project = Project(
            id=project_id,
            name=name,
            path=os.path.abspath(path),
            tech_stack=tech_stack,
            description=description,
        )
        db.add(project)
        await db.commit()

    return {
        "id": project_id,
        "name": name,
        "path": project.path,
        "tech_stack": tech_stack,
        "description": description,
    }


async def start_audit(
    project_id: str,
    mode: str = "smart",
    llm_provider: str = None,
    llm_model: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
    max_turns: int = None,
) -> str:
    """Start an audit for a project. API key can come from .env or runtime param."""
    audit_id = f"audit_{uuid.uuid4().hex[:12]}"
    provider = llm_provider or settings.DEFAULT_LLM_PROVIDER
    if mode not in settings.MODE_META:
        mode = "smart"
    turns = max_turns or settings.MAX_TURNS

    # Get project
    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Create audit record (encrypt any runtime-provided key at rest)
        from app.core.crypto import encrypt_secret
        audit = Audit(
            id=audit_id,
            project_id=project_id,
            mode=mode,
            status="running",
            llm_provider=provider,
            llm_model=llm_model or provider,
            llm_api_key=encrypt_secret(llm_api_key) if llm_api_key else "",
            llm_base_url=llm_base_url or "",
            max_turns=turns,
        )
        db.add(audit)
        await db.commit()

        project_path = project.path
        project_name = project.name
        tech_stack = project.tech_stack

    # Resolve API key (DB > .env) BEFORE launching — fail fast with a clean
    # status instead of leaving a zombie "running" record
    try:
        resolved_key = await _resolve_api_key(provider, llm_api_key)
    except ValueError:
        async with async_session() as db:
            result = await db.execute(select(Audit).where(Audit.id == audit_id))
            audit = result.scalar_one_or_none()
            if audit:
                audit.status = "failed"
                audit.error_message = f"No API key configured for provider '{provider}'"
                audit.completed_at = datetime.now(timezone.utc)
                await db.commit()
        raise

    # Start audit in background (keep a strong ref so GC can't kill it)
    task = asyncio.create_task(_run_audit_task(
        audit_id=audit_id,
        project_path=project_path,
        project_name=project_name,
        tech_stack=tech_stack,
        llm_provider=provider,
        llm_model=llm_model,
        llm_api_key=resolved_key,
        llm_base_url=llm_base_url,
        max_turns=turns,
        mode=mode,
    ))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return audit_id


async def _run_audit_task(
    audit_id: str,
    project_path: str,
    project_name: str,
    tech_stack: list,
    llm_provider: str,
    llm_model: str = "",
    llm_api_key: str = "",
    llm_base_url: str = "",
    max_turns: int = 50,
    mode: str = "smart",
):
    """Background task that runs the actual audit"""
    try:
        # Initialize LLM with runtime or .env config
        llm = LLMFactory.create(
            provider=llm_provider,
            api_key=llm_api_key or None,
            model=llm_model or None,
            base_url=llm_base_url or None,
        )

        # ── Initialize MCP tools ──────────────────────────────────
        mcp_configs = load_merged_mcp_configs()
        mcp_bridge = get_mcp_bridge(mcp_configs)
        if mcp_bridge.is_configured:
            mcp_init_status = await init_mcp_bridge(mcp_configs)
            print(f"  MCP init: {list(mcp_init_status.get('servers', {}).keys())}")
            for srv, s in mcp_init_status.get('servers', {}).items():
                print(f"    [{srv}]: {s.get('status')} ({s.get('tools', 0)} tools)")
        else:
            mcp_bridge = None

        # Engine scans (synchronous, before loop) — AutoCVE-style Scan stage
        scan_result = await asyncio.to_thread(run_engine_scans, project_path, mode)

        # Project file inventory for coverage tracking
        all_files = await asyncio.to_thread(discover_project_files, project_path)

        # Dynamic turn budget: scale with project size
        dyn_turns = max(max_turns, min(200, 30 + len(all_files) // 3))

        memory = MemoryManager()
        skill_mgr = SkillManager()

        # Build skill briefing (relevant skills only, fixed matching)
        skill_briefing = skill_mgr.get_skill_briefing(tech_stack)

        # Initialize state
        state = AgentState(
            audit_id=audit_id,
            project_path=project_path,
            project_name=project_name,
            tech_stack=tech_stack,
            skill_briefing=skill_briefing,
            mode=mode,
            all_files=all_files,
            scan_candidates=scan_result["candidates"],
        )
        # Engine scans already ran synchronously above => mark scan stage done
        state.scanned = True
        if "scan" in settings.MODE_META.get(mode, {}).get("stages", []):
            state.mark_stage("recon")
            state.mark_stage("scan")

        # on_cover callback keeps covered_files updated on every read
        def _on_cover(rel: str):
            state.mark_file_covered(rel)

        tools = CodeAuditTools(project_root=project_path, on_cover=_on_cover)

        # Register tools
        registry = ToolRegistry()
        registry.register(
            name="read_file",
            description="Read a file from the project (size-aware; large files return a head excerpt). Use this to inspect source code.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File relative path, e.g. src/auth/login.py"},
                    "head_only": {"type": "boolean", "description": "Only read the first portion (for large files)", "default": False},
                },
                "required": ["path"],
            },
            handler=tools.read_file,
        )
        registry.register(
            name="read_file_range",
            description="Read a specific line range of a file (for deep-diving large files).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File relative path"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer", "default": 200},
                },
                "required": ["path"],
            },
            handler=tools.read_file_range,
        )
        registry.register(
            name="list_files",
            description="List files in the project matching a glob pattern.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern, e.g. **/*.py. Default: all files"},
                },
            },
            handler=tools.list_files,
        )
        registry.register(
            name="grep",
            description="Search for a regex pattern in project files. Returns matching lines with context.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search"},
                    "path": {"type": "string", "description": "Search scope (directory or file). Default: project root"},
                    "context": {"type": "integer", "description": "Lines of context around matches", "default": 3},
                },
                "required": ["pattern"],
            },
            handler=tools.grep,
        )
        registry.register(
            name="get_project_structure",
            description="Get the project directory tree structure.",
            parameters={"type": "object", "properties": {}},
            handler=tools.get_project_structure,
        )
        # ── engine scan tools (AutoCVE Scan stage) ──
        registry.register(
            name="run_semgrep_scan",
            description="Run Semgrep SAST scan over the project. Returns candidate findings (engine, rule, file, line, message) for triage. Skipped if semgrep not installed.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_semgrep_scan,
        )
        registry.register(
            name="run_sca_scan",
            description="Run dependency (SCA) scan via pip-audit / npm audit. Returns known vulnerable dependencies (CVEs). Skipped if no manifest or scanner.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_sca_scan,
        )
        registry.register(
            name="run_custom_rules",
            description="Run custom YAML detection rules (rule-as-code) over the project.",
            parameters={"type": "object", "properties": {}},
            handler=tools.run_custom_rules,
        )
        # ── skill / verification tools ──
        registry.register(
            name="load_skill",
            description="Load the full content of a security skill pack (SQLi, XSS, SSRF, Path_Traversal, Deserialization, Auth_Bypass, XXE, RCE, File_Upload, Race_Condition, Business_Logic, Crypto, Info_Disclosure, Hardcoded_Secret, Dependency).",
            parameters={
                "type": "object",
                "properties": {"skill_name": {"type": "string", "description": "Skill pack name"}},
                "required": ["skill_name"],
            },
            handler=tools.load_skill,
        )
        registry.register(
            name="verify_poc",
            description="Statically validate (or sandbox-execute if enabled) a PoC script. PoC must be pure-Python stdlib. Returns verified status.",
            parameters={
                "type": "object",
                "properties": {
                    "poc": {"type": "string", "description": "Python PoC script"},
                    "description": {"type": "string", "description": "Optional description of what the PoC does", "default": ""},
                },
                "required": ["poc"],
            },
            handler=tools.verify_poc,
        )
        registry.register(
            name="mark_file_covered",
            description="Explicitly mark a file as audited (use for files you checked and found clean, e.g. docs/tests).",
            parameters={
                "type": "object",
                "properties": {"file_path": {"type": "string", "description": "Relative file path"}},
                "required": ["file_path"],
            },
            handler=tools.mark_file_covered,
        )
        registry.register(
            name="finalize_finding",
            description="Submit a confirmed vulnerability finding. Must include complete taint chain (source to sink).",
            parameters={
                "type": "object",
                "properties": {
                    "vulnerability_type": {
                        "type": "string",
                        "enum": ["SQL_Injection", "XSS", "SSRF", "Path_Traversal", "Deserialization",
                                 "Authentication_Bypass", "Authorization_Failure", "RCE", "XXE",
                                 "Open_Redirect", "Race_Condition", "Business_Logic", "Info_Disclosure",
                                 "Hardcoded_Secret", "Known_Vulnerable_Dependency", "Crypto_Issue"],
                    },
                    "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                    "title": {"type": "string"},
                    "file_path": {"type": "string"},
                    "line_start": {"type": "integer", "default": 0},
                    "line_end": {"type": "integer", "default": 0},
                    "code_snippet": {"type": "string", "default": ""},
                    "description": {"type": "string", "default": ""},
                    "source": {"type": "string", "description": "Taint entry point (user input source)"},
                    "sink": {"type": "string", "description": "Dangerous execution point"},
                    "exploit_chain": {"type": "string", "description": "Complete attack path from source to sink"},
                    "poc": {"type": "string", "default": ""},
                    "suggestion": {"type": "string", "default": ""},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"], "default": "MEDIUM"},
                    "cwe": {"type": "string", "description": "CWE id, e.g. CWE-89 (auto-filled if omitted)", "default": ""},
                },
                "required": ["vulnerability_type", "severity", "title", "file_path",
                             "source", "sink", "exploit_chain"],
            },
            handler=tools.finalize_finding,
        )
        # ── Register MCP tools ────────────────────────────────────
        if mcp_bridge:
            mcp_tool_defs = mcp_bridge.get_tool_definitions()
            for mcp_td in mcp_tool_defs:
                reg_name = mcp_td["function"]["name"]
                reg_desc = mcp_td["function"]["description"]
                reg_params = mcp_td["function"]["parameters"]

                def _mcp_handler(name=reg_name):
                    async def handler(**kwargs):
                        return await mcp_bridge.call_tool(name, kwargs)
                    return handler

                registry.register(
                    name=reg_name,
                    description=reg_desc,
                    parameters=reg_params,
                    handler=_mcp_handler(),
                )
            print(f"  MCP tools registered: {len(mcp_tool_defs)} from {mcp_bridge.server_names}")

        registry.register(
            name="finish_audit",
            description="Call this when you have thoroughly audited all attack surfaces and are done. Pass force=true only if low coverage is acceptable.",
            parameters={
                "type": "object",
                "properties": {"force": {"type": "boolean", "description": "Force finish even with low coverage", "default": False}},
            },
            handler=lambda **kw: '{"status": "audit_finished"}',
        )

        # Run the loop (or parallel orchestrator for large projects)
        from .orchestrator import Orchestrator, chunk_project_files, MIN_FILES_PER_AGENT
        from .specialist_orchestrator import SpecialistOrchestrator

        is_large = len(all_files) > MIN_FILES_PER_AGENT * 2 and len(chunk_project_files(all_files)) > 1

        if is_large and mode in ("smart", "comprehensive"):
            # ── Smart/Comprehensive mode: specialist dispatch (per vulnerability class) ──
            specialist_orch = SpecialistOrchestrator(
                project_path=project_path,
                project_name=project_name,
                tech_stack=tech_stack,
                audit_id=audit_id,
                mode=mode,
                llm_adapter=llm,
                skill_briefing=skill_briefing,
                max_turns=dyn_turns,
            )
            # ── Mark stages BEFORE specialists run (single source of truth) ──
            stages_for_mode = settings.MODE_META.get(mode, {}).get("stages", [])
            for s in stages_for_mode:
                if s != "finalize":
                    state.mark_stage(s)
            spec_result = await specialist_orch.run(all_files, parent_state=state)
            # ── Adversarial verification ──
            verified = await _verify_findings(spec_result["merged"], llm, llm_provider)
            for f in verified:
                state.add_finding(f)
            # Counters already synced via parent_state.increment_counters()
            state.status = "completed"
            state.terminal_reason = "Specialist orchestration: " + ", ".join(spec_result.get("specialists", []))
            state.mark_stage("finalize")
            loop = ReActLoop(state, llm, registry, memory, skill_mgr)
            await loop._save_finding_safe(verified)
            await loop._update_audit_status()
        elif is_large:
            # Parallel multi-agent audit (AutoCVE-style Orchestrator)
            orchestrator = Orchestrator(
                project_path=project_path,
                project_name=project_name,
                tech_stack=tech_stack,
                audit_id=audit_id,
                mode=mode,
                llm_adapter=llm,
                scan_candidates=scan_result["candidates"],
                skill_briefing=skill_briefing,
                max_turns=dyn_turns,
            )
            orch_result = await orchestrator.run(all_files)
            if orch_result["parallel"]:
                # Persist merged findings from all sub-agents
                # ── Adversarial verification (Problem 3) ──
                verified = await _verify_findings(orch_result["merged"], llm, llm_provider)
                for f in verified:
                    state.add_finding(f)
                state.turn = orch_result.get("turns_total", 0)
                state.tool_call_count = orch_result.get("tool_calls_total", 0)
                state.total_tokens = orch_result.get("tokens_total", 0)
                state.status = "completed"
                state.terminal_reason = "Multi-agent orchestration completed"
                state.mark_stage("finalize")
                loop = ReActLoop(state, llm, registry, memory, skill_mgr)
                await loop._save_finding_safe(verified)
                await loop._update_audit_status()
            else:
                loop = ReActLoop(state, llm, registry, memory, skill_mgr, max_turns=dyn_turns)
                await loop.run()
        else:
            loop = ReActLoop(state, llm, registry, memory, skill_mgr, max_turns=dyn_turns)
            await loop.run()
            # ── Adversarial verification (Problem 3) ──
            if state.findings:
                verified = await _verify_findings(state.findings, llm, llm_provider)
                state.findings = verified
                # Re-save findings with verified set (drop rejected)
                await loop._save_finding_safe(verified)

    except Exception as e:
        logger.exception("Audit %s failed", audit_id)
        # Update audit status to failed
        async with async_session() as db:
            result = await db.execute(select(Audit).where(Audit.id == audit_id))
            audit = result.scalar_one_or_none()
            if audit:
                audit.status = "failed"
                audit.error_message = str(e)
                audit.completed_at = datetime.now(timezone.utc)
                await db.commit()
