"""Rule-as-code: load custom YAML detection rules from the rules/ directory.

Rule format (YAML):
```yaml
id: CUSTOM-001
name: Unsafe eval usage
type: RCE
severity: HIGH
languages: [python, php]        # optional; empty = all
patterns:                       # any-of; plain substrings (case-insensitive)
  - "eval("
  - "assert("
exclude_patterns: []            # optional
message: Custom message shown to the LLM
cwe: CWE-95
```
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False


@dataclass
class CustomRule:
    id: str
    name: str
    type: str
    severity: str = "MEDIUM"
    languages: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    message: str = ""
    cwe: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CustomRule":
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            type=str(d.get("type", "Info_Disclosure")),
            severity=str(d.get("severity", "MEDIUM")).upper(),
            languages=[str(x).lower() for x in (d.get("languages") or [])],
            patterns=[str(x) for x in (d.get("patterns") or [])],
            exclude_patterns=[str(x) for x in (d.get("exclude_patterns") or [])],
            message=str(d.get("message", "")),
            cwe=str(d.get("cwe", "")),
        )


def discover_rules(rules_dir: Optional[str] = None) -> List[CustomRule]:
    """Load all *.yml / *.yaml rules from rules_dir (default: settings.RULES_DIR)."""
    if not HAS_YAML:
        return []

    from app.core.config import settings
    base = rules_dir or settings.RULES_DIR
    # Resolve relative to the code-audit project root (backend/.. when run via uvicorn)
    candidates = [
        base,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), "..", base),
    ]
    rules: List[CustomRule] = []
    for root_dir in candidates:
        if not os.path.isdir(root_dir):
            continue
        for fname in sorted(os.listdir(root_dir)):
            if not (fname.endswith(".yml") or fname.endswith(".yaml")):
                continue
            try:
                with open(os.path.join(root_dir, fname), "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict) and data.get("id"):
                    rules.append(CustomRule.from_dict(data))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("id"):
                            rules.append(CustomRule.from_dict(item))
            except Exception:  # noqa: BLE001 — skip malformed rule files
                continue
        if rules:
            break
    return rules


def apply_custom_rules(content: str, filename: str, rules: List[CustomRule]) -> List[dict]:
    """Match custom rules against file content. Returns list of hit dicts."""
    lower = content.lower()
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    hits = []
    for rule in rules:
        if rule.languages:
            lang_map = {
                "python": ["py", "pyw"], "php": ["php", "phtml", "php5"], "js": ["js", "mjs", "cjs"],
                "ts": ["ts", "tsx"], "java": ["java"], "go": ["go"], "ruby": ["rb"],
                "c": ["c", "h"], "cpp": ["cpp", "cc", "hpp"], "cs": ["cs"], "yaml": ["yml", "yaml"],
            }
            langs = set()
            for l in rule.languages:
                langs.update(lang_map.get(l, [l]))
            if ext and ext not in langs:
                continue
        matched = False
        for p in rule.patterns:
            if p.lower() in lower:
                matched = True
                break
        if not matched:
            continue
        if any(p.lower() in lower for p in rule.exclude_patterns):
            continue
        # locate first line of first matched pattern
        line = 1
        for p in rule.patterns:
            idx = lower.find(p.lower())
            if idx >= 0:
                line = content[:idx].count("\n") + 1
                break
        hits.append({
            "engine": "rule",
            "rule_id": rule.id,
            "severity": rule.severity,
            "file_path": filename,
            "line_start": line,
            "line_end": line,
            "message": rule.message or f"Rule {rule.id}: {rule.name}",
            "code": "",
            "metadata": {"name": rule.name, "type": rule.type, "cwe": rule.cwe},
        })
    return hits
