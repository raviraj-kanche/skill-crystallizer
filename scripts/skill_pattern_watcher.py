#!/usr/bin/env python3
"""
skill_pattern_watcher.py — PostToolUse hook: mid-session skill pattern detection.

Fires after each MCP tool call. When a repeating workflow crosses the pattern
threshold, nudges Claude immediately — before the session ends.

Two signal types:
  SKILL GAP        — repeated pattern matches an existing skill's domain.
                     You're doing manually what the skill should handle.
                     → suggest /skill-creator to improve the existing skill.

  NEW SKILL        — repeated pattern, no matching skill exists.
                     → suggest /skill-creator to capture the new workflow.

Fires only once per session (deduped via /tmp flag file).
"""

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

SKILLS_DIR     = Path.home() / ".claude/skills"
MIN_REPEAT     = 3      # a meaningful tool must appear this many times
MIN_MEANINGFUL = 5      # minimum meaningful tool calls in session so far
MIN_DENSITY    = 0.25   # top tool must be >= 25% of meaningful calls

# Too generic to name a skill after
SKIP_TOOLS = {
    "Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent",
    "ToolSearch", "Skill", "ExitPlanMode", "EnterPlanMode",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
}


def nudge_flag(transcript_path: str) -> Path:
    h = hashlib.md5(transcript_path.encode()).hexdigest()[:8]
    return Path(f"/tmp/skill_nudge_{h}")


def already_nudged(transcript_path: str) -> bool:
    return nudge_flag(transcript_path).exists()


def mark_nudged(transcript_path: str):
    nudge_flag(transcript_path).touch()


def extract_tools(transcript_path: str) -> list:
    tool_calls = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "assistant":
                    content = obj.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                name = block.get("name", "")
                                if name:
                                    tool_calls.append(name)
    except Exception:
        pass
    return tool_calls


def detect_pattern(tool_calls: list) -> dict | None:
    counts = Counter(tool_calls)
    meaningful = {t: c for t, c in counts.items() if t not in SKIP_TOOLS}
    total_meaningful = sum(meaningful.values())

    if total_meaningful < MIN_MEANINGFUL:
        return None

    repeated = {t: c for t, c in meaningful.items() if c >= MIN_REPEAT}
    if not repeated:
        return None

    top_tool = max(repeated, key=repeated.get)
    if repeated[top_tool] / total_meaningful < MIN_DENSITY:
        return None

    return {"top_tool": top_tool, "counts": repeated, "total": len(tool_calls)}


def find_matching_skill(top_tool: str) -> str | None:
    """
    Return skill name if an existing skill mentions this tool.
    Checks both the full tool name and the short suffix (e.g. getJiraIssue
    from mcp__claude_ai_Atlassian__getJiraIssue) so MCP tools match cleanly.
    """
    if not SKILLS_DIR.exists():
        return None

    tool_short = top_tool.split("__")[-1].lower()  # getjiraissue, ctx_execute, etc.

    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        # Skip draft skills
        if "draft" in str(skill_md):
            continue
        try:
            content = skill_md.read_text(encoding="utf-8").lower()
            if tool_short in content or top_tool.lower() in content:
                m = re.search(r'^name:\s*(.+)$', skill_md.read_text(encoding="utf-8"), re.MULTILINE)
                if m:
                    return m.group(1).strip()
        except Exception:
            pass
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).exists():
        return

    # Only fire once per session to avoid spamming
    if already_nudged(transcript_path):
        return

    tool_calls = extract_tools(transcript_path)
    pattern = detect_pattern(tool_calls)
    if not pattern:
        return

    mark_nudged(transcript_path)

    top = pattern["top_tool"]
    count_str = "  |  ".join(
        f"{t} {c}×" for t, c in sorted(pattern["counts"].items(), key=lambda x: -x[1])
    )

    matching_skill = find_matching_skill(top)

    if matching_skill:
        print(
            f"\n── SKILL GAP DETECTED ──────────────────────────────────\n"
            f"You're doing manually what '{matching_skill}' should cover:\n"
            f"  {count_str}\n"
            f"Run /skill-creator to improve '{matching_skill}' so this\n"
            f"workflow is captured and doesn't repeat next session.\n"
            f"────────────────────────────────────────────────────────"
        )
    else:
        print(
            f"\n── NEW SKILL OPPORTUNITY ───────────────────────────────\n"
            f"Repeating workflow detected mid-session:\n"
            f"  {count_str}\n"
            f"Run /skill-creator to capture this workflow as a skill.\n"
            f"────────────────────────────────────────────────────────"
        )


if __name__ == "__main__":
    main()
