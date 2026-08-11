"""Memory Manager - Three-layer memory with auto-compact"""

import json
from typing import Optional

from app.core.config import settings


class MemoryManager:
    """Manages working memory (conversation context) with progressive compression"""

    def __init__(self, context_window: int = None, compress_threshold: float = None):
        self.context_window = context_window or settings.CONTEXT_WINDOW_TOKENS
        self.compress_threshold = compress_threshold or settings.COMPRESS_THRESHOLD
        self._estimate_ratio = 4  # approx 4 chars per token

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Rough token estimation"""
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        total_chars += len(str(part.get("text", "")))
            # Tool call overhead
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    total_chars += len(json.dumps(tc, ensure_ascii=False))
        return total_chars // self._estimate_ratio

    def needs_compression(self, messages: list[dict]) -> bool:
        """Check if messages exceed compression threshold"""
        return self.estimate_tokens(messages) > self.context_window * self.compress_threshold

    def compress(self, messages: list[dict], llm_adapter) -> list[dict]:
        """Progressive compression pipeline (4 steps)"""
        if not self.needs_compression(messages):
            return messages

        # Step 1: Truncate tool results
        messages = self._truncate_tool_results(messages)
        messages = self._sanitize_tool_pairs(messages)
        if not self.needs_compression(messages):
            return messages

        # Step 2: Sliding window (keep system + recent + summary of old)
        messages = self._sliding_window(messages)
        messages = self._sanitize_tool_pairs(messages)
        if not self.needs_compression(messages):
            return messages

        # Step 3: Micro-compact (merge consecutive tool results, strip whitespace)
        messages = self._micro_compact(messages)
        messages = self._sanitize_tool_pairs(messages)
        if not self.needs_compression(messages):
            return messages

        # Step 4: LLM summary (most expensive, last resort)
        # This is async in practice but we handle it at the loop level
        return messages  # Caller handles LLM summary

    def _sanitize_tool_pairs(self, messages: list[dict]) -> list[dict]:
        """Ensure every role='tool' message has a preceding assistant message
        with matching tool_calls (by tool_call_id). Drop orphans that would
        trigger 'tool must follow tool_calls' 400 errors from the LLM API.

        Also drops assistant messages whose tool_calls have no following tool
        response (incomplete pair) — strictly, OpenAI/DeepSeek allow this,
        but pairing is safer for providers that error on it.
        """
        result = []
        pending_tool_call_ids = set()

        for msg in messages:
            role = msg.get("role")

            if role == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id and tc_id in pending_tool_call_ids:
                    result.append(msg)
                    pending_tool_call_ids.discard(tc_id)
                else:
                    # Orphan tool message (preceding assistant had no matching tool_calls)
                    # Drop it to avoid 400.
                    continue

            elif role == "assistant" and msg.get("tool_calls"):
                # Track which tool_call_ids this assistant expects responses for
                ids = {tc.get("id") for tc in msg.get("tool_calls", []) if tc.get("id")}
                pending_tool_call_ids.update(ids)
                result.append(msg)

            else:
                # user / system / assistant-without-tool-calls
                # If we're entering a non-tool block and still have pending IDs,
                # those assistant.tool_calls were never responded to. Drop them
                # to keep the pair invariant clean.
                if role != "assistant" and pending_tool_call_ids:
                    # Walk back: remove the last assistant message that had these IDs
                    while result and result[-1].get("role") == "assistant" and result[-1].get("tool_calls"):
                        last_ids = {tc.get("id") for tc in result[-1].get("tool_calls", []) if tc.get("id")}
                        if last_ids & pending_tool_call_ids:
                            result.pop()
                            pending_tool_call_ids -= last_ids
                        else:
                            break
                result.append(msg)

        return result

    def _truncate_tool_results(self, messages: list[dict]) -> list[dict]:
        """Step 1: Truncate large tool results to budget"""
        budget = settings.TOOL_RESULT_BUDGET
        result = []
        for msg in messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > budget:
                    msg = {**msg, "content": content[:budget] + f"\n... [truncated at {budget} chars]"}
            result.append(msg)
        return result



    def _structured_compress(self, old_messages: list[dict]) -> dict:
        '''Build structured summary preserving audit decisions.'''
        files_vulnerable = []
        files_safe = set()
        attack_surfaces = set()
        findings_count = 0
        key_results = {}

        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "assistant" and msg.get("tool_calls"):
                for tc in msg.get("tool_calls", []):
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    if name == "finalize_finding":
                        findings_count += 1
                        try:
                            args = fn.get("arguments", {})
                            if isinstance(args, str):
                                import json as j
                                args = j.loads(args)
                            files_vulnerable.append({
                                "file": args.get("file_path", "?"),
                                "type": args.get("vulnerability_type", "?"),
                                "sink": args.get("sink", "?")[:80],
                            })
                        except Exception:
                            pass

            if role == "tool":
                tool_name = msg.get("tool_name", "")
                result = content if isinstance(content, str) else ""
                lower = result.lower()
                if tool_name == "grep" and "matches" in lower:
                    try:
                        import json as j
                        data = j.loads(result)
                        files = list(set(m.get("path", "?") for m in data.get("matches", [])))
                        if files:
                            key_results["grep"] = f"{data.get('count', 0)} hits in {len(files)} files"
                    except Exception:
                        pass
                if any(kw in lower for kw in ["safe", "parameterized", "no vulnerability",
                                              "properly escaped", "安全", "无误"]):
                    files_safe.add("verified")

        summary = {
            "files_vulnerable": files_vulnerable[:15],
            "files_safe_count": len(files_safe),
            "findings_submitted": findings_count,
            "key_scans": key_results,
            "messages_compressed": len(old_messages),
        }
        return summary

    def _format_structured_summary(self, summary: dict) -> str:
        parts = [f"[Audit Progress] Compressed {summary['messages_compressed']} messages."]
        if summary["findings_submitted"]:
            parts.append(f"Findings so far: {summary['findings_submitted']}")
        if summary["files_vulnerable"]:
            vuln = ["  - " + v["file"] + ": " + v["type"] for v in summary["files_vulnerable"][:10]]
            parts.append("Vulnerable files:\n" + "\n".join(vuln))
        if summary["files_safe_count"]:
            parts.append(f"Files verified safe: {summary['files_safe_count']}")
        if summary["key_scans"]:
            parts.append("Scans: " + "; ".join(f"{k}:{v}" for k, v in summary["key_scans"].items()))
        return ". ".join(parts) + "."

    def _sliding_window(self, messages: list[dict]) -> list[dict]:
        '''Enhanced sliding window with finding protection and structured compression.'''
        keep_recent = 12
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if len(non_system) <= keep_recent:
            return messages

        # Protect findings: never compress anything after first finding submission
        finding_start = len(non_system)
        for i, msg in enumerate(non_system):
            for tc in msg.get("tool_calls", []):
                name = tc.get("function", {}).get("name", "")
                if name == "finalize_finding":
                    finding_start = min(finding_start, i)
                    break

        if finding_start <= keep_recent:
            old = non_system[:finding_start]
            recent = non_system[finding_start:]
        else:
            old = non_system[:finding_start - keep_recent]
            recent = non_system[finding_start - keep_recent:]

        if not old:
            return messages

        summary = self._structured_compress(old)
        summary_msg = {
            "role": "user",
            "content": self._format_structured_summary(summary),
        }
        return system_msgs + [summary_msg] + recent


    def _quick_summarize_old(self, old_messages: list[dict]) -> str:
        """Quick heuristic summary without LLM"""
        files_checked = set()
        tools_used = []
        findings = []

        for msg in old_messages:
            if msg.get("role") == "tool":
                tool_name = msg.get("tool_name", "")
                tools_used.append(tool_name)
                # Try to extract file paths from tool results
                content = msg.get("content", "")
                if "path" in content:
                    try:
                        data = json.loads(content)
                        if "path" in data:
                            files_checked.add(data["path"])
                    except json.JSONDecodeError:
                        pass
            elif msg.get("role") == "assistant":
                content = msg.get("content", "")
                if "finalize" in content.lower() or "vulnerability" in content.lower():
                    findings.append("vulnerability mentioned")

        parts = []
        if files_checked:
            parts.append(f"Files checked: {', '.join(list(files_checked)[:10])}")
        if tools_used:
            parts.append(f"Tools used: {', '.join(set(tools_used))}")
        if findings:
            parts.append(f"Findings: {len(findings)} mentioned")
        parts.append(f"Messages compressed: {len(old_messages)}")

        return ". ".join(parts) + "."

    def _micro_compact(self, messages: list[dict]) -> list[dict]:
        """Step 3: Merge consecutive tool results, strip redundant whitespace"""
        result = []
        i = 0
        while i < len(messages):
            msg = messages[i]

            # Merge consecutive tool results
            if msg.get("role") == "tool":
                merged_content = msg.get("content", "")
                merged_count = 1
                while (i + 1 < len(messages) and
                       messages[i + 1].get("role") == "tool" and
                       messages[i + 1].get("tool_name") == msg.get("tool_name")):
                    i += 1
                    next_content = messages[i].get("content", "")
                    if len(merged_content) + len(next_content) < settings.TOOL_RESULT_BUDGET:
                        merged_content += "\n---\n" + next_content
                        merged_count += 1

                if merged_count > 1:
                    msg = {**msg, "content": f"[{merged_count} results merged]\n{merged_content}"}

            # Strip excessive whitespace
            if isinstance(msg.get("content"), str):
                content = msg["content"]
                # Replace multiple blank lines with single
                while "\n\n\n" in content:
                    content = content.replace("\n\n\n", "\n\n")
                msg = {**msg, "content": content}

            result.append(msg)
            i += 1

        return result

    async def llm_summarize(self, messages: list[dict], llm_adapter) -> list[dict]:
        """Step 4: Use LLM to summarize old messages (most expensive)"""
        # Sanitize first to avoid carrying orphan tool messages into the split
        messages = self._sanitize_tool_pairs(messages)

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if len(non_system) <= 10:
            return messages

        # Find a safe split boundary that doesn't orphan tool pairs.
        # Walk backward from midpoint to find a non-assistant-tool-call position.
        boundary = len(non_system) // 2
        # If the message at boundary is a tool, shift boundary to start at its assistant.
        while boundary < len(non_system) and non_system[boundary].get("role") == "tool":
            boundary -= 1
        # If the message just before boundary is an assistant with tool_calls,
        # we need to include the assistant too OR drop it. Simpler: shift forward
        # so the assistant stays in 'old' with its tool responses.
        while boundary > 0 and non_system[boundary - 1].get("role") == "assistant" and non_system[boundary - 1].get("tool_calls"):
            boundary -= 1

        old = non_system[:boundary]
        recent = non_system[boundary:]

        if not old:
            return messages

        summary = await llm_adapter.summarize(old)
        summary_msg = {
            "role": "user",
            "content": f"[Auto-Compact Summary] Previous audit context has been compressed:\n{summary}",
        }

        result = system_msgs + [summary_msg] + recent
        # Final safety pass
        return self._sanitize_tool_pairs(result)
