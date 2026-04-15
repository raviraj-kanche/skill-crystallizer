#!/usr/bin/env python3
"""
skill_auto_drafter.py — Stop hook: auto-generates draft skills from session patterns.

Reads the Claude Code session transcript, detects repeated tool workflows,
and writes a draft SKILL.md to ~/.claude/skills/draft/ when a genuine
repeating pattern is found (no raw tool count threshold needed).

Fires AFTER vault_search.py save-session via the Stop hook chain.
Reads Stop hook payload from stdin.

Pattern logic:
  - A meaningful (non-generic) tool must appear MIN_REPEAT+ times
  - Total meaningful tool calls must be >= MIN_MEANINGFUL
  - Top tool must be >= MIN_DENSITY (25%) of meaningful calls — filters noise in long exploratory sessions
  - Raw total call count is NOT used — measures pattern strength, not session length
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DRAFT_DIR       = Path.home() / ".claude/skills/draft"
MIN_REPEAT      = 3     # meaningful tool must appear this many times
MIN_MEANINGFUL  = 5     # at least this many meaningful tool calls total
MIN_DENSITY     = 0.25  # top tool must be >= 25% of meaningful calls

# Generic tools — too broad to name a skill after
SKIP_TOOLS = {"Bash", "Read", "Write", "Edit", "Glob", "Grep", "Agent"}


def extract_tools_and_messages(transcript_path: str):
    """Extract tool call names and early user messages from JSONL transcript."""
    tool_calls    = []
    user_messages = []

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

                event_type = obj.get("type", "")
                message    = obj.get("message", {})
                content    = message.get("content", "")

                # Extract tool_use names from assistant messages
                if event_type == "assistant" and isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "")
                            if name:
                                tool_calls.append(name)

                # Collect first 4 user messages for keyword extraction
                if event_type == "user" and len(user_messages) < 4:
                    if isinstance(content, str):
                        user_messages.append(content.strip())
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "").strip()
                                if text and not text.startswith("<"):
                                    user_messages.append(text)
                                    break
    except Exception:
        pass

    return tool_calls, user_messages


def detect_pattern(tool_calls: list, user_messages: list):
    """Return the dominant non-generic tool pattern, or None if nothing found."""
    counts = Counter(tool_calls)

    # Separate meaningful from generic tool calls
    meaningful = {t: c for t, c in counts.items() if t not in SKIP_TOOLS}
    total_meaningful = sum(meaningful.values())

    # Gate 1: enough meaningful tool calls in the session
    if total_meaningful < MIN_MEANINGFUL:
        return None

    # Gate 2: at least one meaningful tool repeated MIN_REPEAT+ times
    repeated = {t: c for t, c in meaningful.items() if c >= MIN_REPEAT}
    if not repeated:
        return None

    top_tool = max(repeated, key=repeated.get)

    # Gate 3: pattern density — top tool must be >= MIN_DENSITY of meaningful calls
    density = repeated[top_tool] / total_meaningful
    if density < MIN_DENSITY:
        return None

    # Extract keywords from early user messages for skill naming

    noise = {
        "this", "that", "with", "from", "have", "will", "want", "need",
        "just", "also", "please", "help", "what", "when", "then", "here",
        "there", "should", "would", "could", "been", "your", "their",
    }
    keywords = []
    seen     = set()
    for msg in user_messages:
        for word in re.findall(r'\b[a-z]{4,}\b', msg.lower()):
            if word not in noise and word not in seen:
                seen.add(word)
                keywords.append(word)
            if len(keywords) >= 8:
                break
        if len(keywords) >= 8:
            break

    return {
        "top_tool":    top_tool,
        "counts":      repeated,
        "all_counts":  counts,
        "keywords":    keywords,
        "total_tools": len(tool_calls),
    }


def slug(words: list, fallback: str) -> str:
    raw = "-".join(words[:3]) if words else fallback
    return re.sub(r"[^a-z0-9-]", "", raw.lower()).strip("-") or "auto-skill"


def generate_draft(pattern: dict) -> tuple[str, str]:
    """Return (skill_name, SKILL.md content)."""
    top    = pattern["top_tool"]
    counts = pattern["counts"]
    kw     = pattern["keywords"]
    total  = pattern["total_tools"]
    today  = datetime.now().strftime("%Y-%m-%d")

    name   = slug(kw, top.lower().replace("_", "-"))
    title  = name.replace("-", " ").title()

    tool_lines = "\n".join(
        f">   - **{t}**: {c}×"
        for t, c in sorted(counts.items(), key=lambda x: -x[1])
    )
    all_summary = ", ".join(
        f"{t}({c})" for t, c in pattern["all_counts"].most_common(8)
    )
    vault_query = " ".join(kw[:3])

    content = f"""---
name: {name}
description: >
  DRAFT — auto-generated {today}. Captures the {title} workflow
  detected from a session with {total} tool calls. Review and complete before activating.
draft: true
---

# {title}  ← DRAFT — Review Required

> Auto-drafted {today} from a session where these tools repeated:
{tool_lines}
>
> Full session tool usage: {all_summary}

---

## When to Use

<!-- Describe the trigger — when should this skill activate? -->
<!-- Session keywords detected: {", ".join(kw)} -->

User is working on: [fill in based on the repeated workflow above]

## Steps

<!-- Reconstruct the exact workflow from the session. -->
<!-- Tip: run this to pull the session transcript: -->
<!-- /vault-search {vault_query} --type sessions -->

1. [Step 1 — fill in]
2. [Step 2 — fill in]
3. [Step 3 — fill in]

## Output

[Describe what this skill produces and where it saves it]

## Notes

- Primary tool detected: **{top}** ({counts.get(top, 0)}×)
- Generated from {total}-tool-call session on {today}

## Before Activating

- [ ] Rename skill file and `name:` field if needed
- [ ] Fill in all sections above
- [ ] Remove `draft: true` from frontmatter
- [ ] Test with `/skill-creator` to register
"""
    return name, content


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = {}

    transcript_path = payload.get("transcript_path", "")
    if not transcript_path or not Path(transcript_path).exists():
        return

    tool_calls, user_messages = extract_tools_and_messages(transcript_path)
    pattern = detect_pattern(tool_calls, user_messages)

    if not pattern:
        return

    # Write the draft
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    name, content = generate_draft(pattern)
    draft_path = DRAFT_DIR / f"{name}.md"
    draft_path.write_text(content, encoding="utf-8")

    # Nudge output — printed into Claude's context at session end
    count_str = "  |  ".join(
        f"{t} {c}×" for t, c in sorted(pattern["counts"].items(), key=lambda x: -x[1])
    )
    print(
        f"\n── SKILL NUDGE ─────────────────────────────────────────\n"
        f"Repeating workflow detected this session:\n"
        f"  {count_str}\n"
        f"Draft skill saved → {draft_path}\n"
        f"Review it and run /review-drafts next session to activate or discard.\n"
        f"────────────────────────────────────────────────────────"
    )


if __name__ == "__main__":
    main()
