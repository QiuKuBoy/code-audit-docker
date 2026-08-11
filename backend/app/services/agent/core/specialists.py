
"""Specialist and Verifier Agents for enhanced code audit."""

from __future__ import annotations

import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.agent.core.state import FindingRecord


@dataclass
class SpecialistProfile:
    bug_class: str
    display_name: str
    trigger_patterns: list[str]
    focus_prompt: str
    checklist: list[str]
    priority: int = 0


SPECIALISTS = {
    "sqli": SpecialistProfile(
        bug_class="SQL_Injection",
        display_name="SQL Injection Specialist",
        trigger_patterns=[
            r"\.execute\(", r"\.query\(", r"mysql_query", r"pg_query",
            r"jdbcTemplate", r"createNativeQuery", r"\$\{.*sql",
            r"SELECT.*\+", r"WHERE.*\$", r"orderBy\(",
            r"\.raw\(", r"db\.exec", r"cursor\.execute",
        ],
        focus_prompt=(
            "You are a SQL Injection specialist. Your ONLY task is to find "
            "SQL injection vulnerabilities. Look for:\n"
            "1. String concatenation in SQL queries\n"
            "2. Dynamic ORDER BY / GROUP BY without whitelist\n"
            "3. LIKE clauses with unescaped user input\n"
            "4. ${} interpolation in MyBatis/XML mappers\n"
            "5. Raw/execute without parameterization\n"
            "ONLY submit findings with a verified Source to Sink chain."
        ),
        checklist=[
            "All SQL queries parameterized?",
            "Dynamic ORDER BY / GROUP BY whitelisted?",
            "MyBatis ${} controllable by user input?",
            "LIKE query wildcards safe?",
            "Stored procedure params validated?",
        ],
        priority=0,
    ),
    "xss": SpecialistProfile(
        bug_class="XSS",
        display_name="XSS Specialist",
        trigger_patterns=[
            r"th:utext", r"innerHTML", r"dangerouslySetInnerHTML",
            r"\.html\(", r"document\.write", r"eval\(",
            r"v-html", r"\{\{\{.*\}\}\}", r"bypassSecurityTrust",
            r"echo\s", r"print\s", r"<?=.*\$",
        ],
        focus_prompt=(
            "You are an XSS specialist. Look for unescaped output in HTML "
            "context, user input rendered without sanitization, and CSP bypass vectors."
        ),
        checklist=[
            "HTML output escaped (escapeHtml/encode)?",
            "th:utext/innerHTML source controllable?",
            "Rich text editor output filtered?",
            "CSP correctly configured?",
            "JSON embedded in HTML safe?",
        ],
        priority=1,
    ),
    "auth_bypass": SpecialistProfile(
        bug_class="Authentication_Bypass",
        display_name="Auth Bypass Specialist",
        trigger_patterns=[
            r"@PreAuthorize", r"@RequiresPermissions", r"@RequiresRoles",
            r"Shiro", r"Spring Security", r"check_login", r"isAuthenticated",
            r"getSession", r"X-Forwarded-For",
            r"X-Real-IP", r"getRemoteAddr", r"request\.getHeader",
        ],
        focus_prompt=(
            "You are an Authentication/Authorization specialist. Look for "
            "missing auth annotations, client-controlled identity headers, "
            "session fixation, IDOR, and JWT validation issues."
        ),
        checklist=[
            "Sensitive endpoints have auth annotations?",
            "IP whitelist bypassable via X-Forwarded-For?",
            "Horizontal privilege escalation (IDOR)?",
            "JWT algorithm rejects none?",
            "Session ID regenerated after login?",
        ],
        priority=0,
    ),
    "deserialization": SpecialistProfile(
        bug_class="Deserialization",
        display_name="Deserialization Specialist",
        trigger_patterns=[
            r"ObjectInputStream", r"readObject", r"Serializable",
            r"unserialize\(", r"pickle\.load", r"yaml\.load\(",
            r"Yaml\(\)", r"fromXML", r"XMLDecoder",
            r"fastjson", r"jackson.*enableDefaultTyping",
        ],
        focus_prompt=(
            "You are a Deserialization specialist. Look for unsafe object "
            "deserialization with untrusted data."
        ),
        checklist=[
            "Deserialization input from user?",
            "Jackson enableDefaultTyping enabled?",
            "Type whitelist in place?",
            "Python using yaml.safe_load?",
            "PHP unserialize signature-verified?",
        ],
        priority=2,
    ),
    "path_traversal": SpecialistProfile(
        bug_class="Path_Traversal",
        display_name="Path Traversal Specialist",
        trigger_patterns=[
            r"File\(.*\+", r"new File", r"FileReader", r"FileWriter",
            r"file_get_contents", r"fopen", r"readFile", r"writeFile",
            r"downloadFile", r"getResourceAsStream", r"Paths\.get",
            r"\.\./", r"%2e%2e", r"\.\.\\\\",
        ],
        focus_prompt=(
            "You are a Path Traversal specialist. Look for file operations "
            "where the path is influenced by user input without proper validation."
        ),
        checklist=[
            "File path from user input?",
            "../ filtered (check encoding bypass)?",
            "getCanonicalPath used for normalization?",
            "Download interface has directory restriction?",
            "ZIP slip attack vector?",
        ],
        priority=1,
    ),
    "rce": SpecialistProfile(
        bug_class="RCE",
        display_name="RCE Specialist",
        trigger_patterns=[
            r"Runtime\.getRuntime\(\)", r"ProcessBuilder",
            r"exec\(", r"system\(", r"shell_exec", r"popen",
            r"os\.system", r"subprocess\.", r"eval\(",
            r"assert\(", r"create_function", r"preg_replace.*\/e",
        ],
        focus_prompt=(
            "You are an RCE specialist. Look for any code path where user "
            "input reaches a command execution or code evaluation function."
        ),
        checklist=[
            "User input reaches exec/system/eval?",
            "Shell command properly escaped?",
            "Eval-like functions with dynamic code?",
            "Template injection vectors (SSTI)?",
            "Expression language injection (EL/SpEL/OGNL)?",
        ],
        priority=1,
    ),
}


def get_specialists_for_triggers(triggers_found: set[str]) -> list[SpecialistProfile]:
    specialists = []
    for name, profile in SPECIALISTS.items():
        matched = any(
            any(t in trigger for t in profile.trigger_patterns)
            for trigger in triggers_found
        )
        if matched:
            specialists.append(profile)
    for name in ["auth_bypass", "sqli"]:
        profile = SPECIALISTS.get(name)
        if profile and profile not in specialists:
            specialists.append(profile)
    specialists.sort(key=lambda s: s.priority)
    return specialists


@dataclass
class VerifierResult:
    finding: FindingRecord
    verdict: str
    confidence: str
    reasoning: str
    alternative_model: str = ""
    suggested_fix: str = ""


class FindingVerifier:
    """Cross-validates findings using an alternative LLM model."""

    def __init__(self, primary_adapter, secondary_adapter=None):
        self.primary = primary_adapter
        self.secondary = secondary_adapter or primary_adapter

    async def verify(self, finding: FindingRecord, code_context: str = "") -> VerifierResult:
        prompt = f"""You are a skeptical security reviewer. Review this finding:

Type: {finding.vulnerability_type}
Severity: {finding.severity}
Title: {finding.title}
File: {finding.file_path}:{finding.line_start}-{finding.line_end}
Source: {finding.source}
Sink: {finding.sink}
Exploit chain: {finding.exploit_chain}
Description: {finding.description}

Determine if this is REAL or FALSE POSITIVE:
- ACCEPTED: Real vulnerability, exploit chain valid
- REJECTED: False positive (explain why)
- NEEDS_MORE_INFO: Need more code context

Respond with JSON only:
{{"verdict": "ACCEPTED|REJECTED|NEEDS_MORE_INFO",
 "confidence": "HIGH|MEDIUM|LOW",
 "reasoning": "one-line explanation",
 "suggested_fix": "one-line fix approach if ACCEPTED"}}"""

        messages = [
            {"role": "system", "content": "Security verification agent. Output JSON only."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.secondary.chat(messages, tools=None)
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content)
        except Exception:
            result = {"verdict": "NEEDS_MORE_INFO", "confidence": "LOW",
                      "reasoning": "Verification call failed", "suggested_fix": ""}

        return VerifierResult(
            finding=finding,
            verdict=result.get("verdict", "NEEDS_MORE_INFO"),
            confidence=result.get("confidence", "LOW"),
            reasoning=result.get("reasoning", ""),
            alternative_model=getattr(self.secondary, "model", "unknown"),
            suggested_fix=result.get("suggested_fix", ""),
        )

    async def verify_batch(self, findings: list[FindingRecord]) -> list[VerifierResult]:
        results = await asyncio.gather(*[self.verify(f) for f in findings])
        return list(results)


def build_specialist_prompt(profile: SpecialistProfile, base_prompt: str, files: list[str]) -> str:
    file_list = ", ".join(files[:30])
    if len(files) > 30:
        file_list += f"\n... and {len(files) - 30} more files"

    specialist_block = f"""
# Specialist Agent: {profile.display_name}
{profile.focus_prompt}

## Assigned Files ({len(files)} total)
{file_list}

## Audit Checklist
"""
    for i, item in enumerate(profile.checklist, 1):
        specialist_block += f"{i}. {item}\n"

    if "# Audit Mode" in base_prompt:
        return base_prompt.replace("# Audit Mode", specialist_block + "\n# Audit Mode")
    return base_prompt + "\n" + specialist_block
