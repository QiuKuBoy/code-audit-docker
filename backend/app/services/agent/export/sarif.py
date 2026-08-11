"""SARIF export + CWE/CVSS mapping for findings.

Provides:
- cwe_for_type(vulnerability_type)  -> primary CWE id
- cvss_base_score(severity)         -> CVSS 3.1 base score estimate
- build_sarif(findings, project)    -> SARIF 2.1.0 JSON dict
"""

from __future__ import annotations

from typing import List

# Primary CWE per vulnerability type (OWASP-aligned)
TYPE_CWE = {
    "SQL_Injection": "CWE-89",
    "XSS": "CWE-79",
    "SSRF": "CWE-918",
    "Path_Traversal": "CWE-22",
    "Deserialization": "CWE-502",
    "Authentication_Bypass": "CWE-287",
    "Authorization_Failure": "CWE-862",
    "RCE": "CWE-78",
    "XXE": "CWE-611",
    "Open_Redirect": "CWE-601",
    "Race_Condition": "CWE-362",
    "Business_Logic": "CWE-840",
    "Info_Disclosure": "CWE-200",
    "Hardcoded_Secret": "CWE-798",
    "Known_Vulnerable_Dependency": "CWE-1104",
}

SEVERITY_CVSS = {
    "CRITICAL": 9.8,
    "HIGH": 7.5,
    "MEDIUM": 5.0,
    "LOW": 2.5,
}


def cwe_for_type(vtype: str) -> str:
    return TYPE_CWE.get(vtype, "CWE-710")


def cvss_base_score(severity: str) -> float:
    return SEVERITY_CVSS.get((severity or "MEDIUM").upper(), 5.0)


def build_sarif(findings: List, project_name: str = "project", tool_name: str = "code-audit-agent") -> dict:
    """findings: list of objects with attributes used by the report exporter."""
    results = []
    for f in findings:
        sev = (f.severity or "MEDIUM").upper()
        results.append({
            "ruleId": f.vulnerability_type,
            "level": "error" if sev == "CRITICAL" else ("warning" if sev == "HIGH" else "note"),
            "message": {"text": f.title or f.description or ""},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file_path or ""},
                    "region": {
                        "startLine": f.line_start or 1,
                        "endLine": f.line_end or (f.line_start or 1),
                    } if (f.line_start or f.line_end) else {},
                }
            }],
            "properties": {
                "severity": sev,
                "confidence": f.confidence or "MEDIUM",
                "cwe": cwe_for_type(f.vulnerability_type),
                "cvss": cvss_base_score(sev),
                "source": getattr(f, "source", "") or "",
                "sink": getattr(f, "sink", "") or "",
            },
        })

    rules = {}
    for f in findings:
        rules[f.vulnerability_type] = {
            "id": f.vulnerability_type,
            "shortDescription": {"text": f.vulnerability_type},
            "helpUri": f"https://cwe.mitre.org/data/definitions/{cwe_for_type(f.vulnerability_type).split('-')[1]}.html",
            "properties": {"cwe": cwe_for_type(f.vulnerability_type)},
        }

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": tool_name,
                    "version": "1.2.0",
                    "informationUri": "https://github.com/larlarua/AutoCVE",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }],
    }
