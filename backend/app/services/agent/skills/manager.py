"""Skill Manager - Load and inject security knowledge packs.

Fixed vs original:
- matches() no longer returns True unconditionally (dead-code bug): now matches
  by tech stack / language keywords, or when the skill is marked always-relevant.
- briefing is built structurally (overview + patterns + checklist excerpt)
  instead of a raw 500-char head slice.
- Skills can be loaded on demand (full content) via the load_skill tool.
"""

import os
import re
from typing import List, Optional

# Keywords that map a skill to languages / frameworks.
# A skill matches if ANY of its keywords appears in the project tech stack.
SKILL_KEYWORDS = {
    "sqli": ["sql", "mysql", "postgres", "database", "python", "php", "java", "go", "node", "javascript", "jdbc", "mybatis", "sqlalchemy", "django", "flask", "express"],
    "xss": ["web", "html", "javascript", "react", "vue", "angular", "php", "jsp", "frontend", "django", "flask", "express", "next"],
    "ssrf": ["web", "url", "http", "fetch", "requests", "curl", "file_get_contents", "python", "php", "node", "java", "go"],
    "path_traversal": ["file", "fs", "path", "download", "upload", "python", "php", "java", "node", "go", "c", "cpp"],
    "deserialization": ["serialize", "unserialize", "pickle", "json", "objectinputstream", "yaml", "java", "python", "php", "ruby"],
    "auth_bypass": ["login", "auth", "session", "token", "jwt", "oauth", "cookie", "password", "django", "flask", "spring", "express", "php"],
    "xxe": ["xml", "simplexml", "dom", "sax", "xmlreader", "java", "php", "python", ".net", "c#"],
    "rce": ["exec", "system", "shell", "command", "eval", "python", "php", "java", "node", "go", "c", "cpp", "ruby"],
    "file_upload": ["upload", "multipart", "move_uploaded_file", "file", "django", "flask", "spring", "express", "php"],
    "race_condition": ["transaction", "lock", "balance", "order", "payment", "callback", "thread", "async", "concurrent", "python", "php", "java", "node", "go"],
    "business_logic": ["order", "payment", "price", "cart", "coupon", "refund", "wallet", "recharge", "python", "php", "java", "node", "go"],
    "crypto": ["crypto", "hash", "encrypt", "aes", "rsa", "md5", "sha", "bcrypt", "jwt", "secret", "key"],
    "info_disclosure": ["config", "debug", "log", "error", "secret", "key", "token", "env", "credential", "password"],
    "hardcoded_secret": ["secret", "accesskey", "apikey", "password", "token", "credential", "private_key", "config"],
    "dependency": ["requirements.txt", "package.json", "package-lock", "pom.xml", "build.gradle", "go.mod", "cargo.toml", "composer.json"],
}

# Skills that are always relevant regardless of tech stack (broad applicability).
ALWAYS_RELEVANT = {"sqli", "auth_bypass", "info_disclosure", "hardcoded_secret"}


class Skill:
    """A security knowledge skill pack"""

    def __init__(self, name: str, skill_dir: str):
        self.name = name
        self.skill_dir = skill_dir
        self.briefing: str = ""
        self.full_content: str = ""
        self.checklists: dict = {}
        self._load()

    def _load(self):
        """Load SKILL.md and checklists"""
        skill_md = os.path.join(self.skill_dir, "SKILL.md")
        if os.path.isfile(skill_md):
            with open(skill_md, "r", encoding="utf-8") as f:
                self.full_content = f.read()
            self.briefing = self._build_briefing(self.full_content)

        # Load checklists
        checklist_dir = os.path.join(self.skill_dir, "checklists")
        if os.path.isdir(checklist_dir):
            for fname in os.listdir(checklist_dir):
                if fname.endswith(".md"):
                    lang = fname.replace(".md", "")
                    with open(os.path.join(checklist_dir, fname), "r", encoding="utf-8") as f:
                        self.checklists[lang] = f.read()

    @staticmethod
    def _build_briefing(full: str, max_len: int = 800) -> str:
        """Build a structural briefing: Overview + Methodology + patterns/keywords."""
        lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
        overview = ""
        methodology = []
        in_method = False
        for ln in lines:
            if ln.lower().startswith("# overview") or ln.lower().startswith("## overview"):
                overview = ""
                in_method = False
                continue
            if ln.lower().startswith("# ") or ln.lower().startswith("## "):
                in_method = ln.lower().startswith("## methodology") or ln.lower().startswith("## audit")
                if not in_method and not overview:
                    overview = ln.lstrip("# ").strip()
                continue
            if in_method and ln and not ln.startswith("```"):
                methodology.append(ln[:160])
        parts = []
        if overview:
            parts.append(f"Overview: {overview}")
        if methodology:
            parts.append("Method: " + " | ".join(methodology[:6]))
        brief = "; ".join(parts)
        return brief[:max_len] if brief else full[:max_len]

    def matches(self, tech_stack: List[str]) -> bool:
        """Match skill against tech stack. Fixed: no unconditional True."""
        if self.name in ALWAYS_RELEVANT:
            return True
        keywords = SKILL_KEYWORDS.get(self.name, [])
        if not keywords:
            return True  # unknown skill: include by default (conservative)
        tech_lower = [t.lower() for t in tech_stack]
        for tech in tech_lower:
            for kw in keywords:
                if kw in tech:
                    return True
        return False


class SkillManager:
    """Manages skill packs and injects them into agent context"""

    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            # Default to project root /skills (code-audit/skills)
            # manager.py -> skills -> agent -> services -> app -> backend -> project root
            skills_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))),
                "skills"
            )
        self.skills_dir = skills_dir
        self.skills: dict[str, Skill] = {}
        self._discover()

    def _discover(self):
        """Find all skill packs"""
        if not os.path.isdir(self.skills_dir):
            return
        for name in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, name)
            if os.path.isdir(skill_path) and os.path.isfile(os.path.join(skill_path, "SKILL.md")):
                self.skills[name] = Skill(name, skill_path)

    def get_skill_briefing(self, tech_stack: List[str]) -> str:
        """Get briefing text for relevant skills only (fixed matching)."""
        briefings = []
        for name, skill in self.skills.items():
            if skill.matches(tech_stack) and skill.briefing:
                briefings.append(f"## {name}\n{skill.briefing}")
        return "\n\n".join(briefings) if briefings else ""

    def get_full_skill(self, skill_name: str) -> Optional[str]:
        """Load full skill content by name"""
        skill = self.skills.get(skill_name)
        return skill.full_content if skill else None

    def get_checklist(self, skill_name: str, language: str) -> Optional[str]:
        """Get a specific language checklist"""
        skill = self.skills.get(skill_name)
        if skill:
            return skill.checklists.get(language)
        return None

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())

    def skill_names_with_briefing(self) -> List[str]:
        return [n for n, s in self.skills.items() if s.briefing]
