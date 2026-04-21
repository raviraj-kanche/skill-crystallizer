# skill-crystallizer

> Stop explaining your workflows every time you start a new Claude session.

`skill-crystallizer` is a Claude Code plugin with two detection layers:

- **Mid-session** (`skill_pattern_watcher.py`) — fires after every MCP tool call. When a repeating pattern crosses the threshold, nudges you immediately to run `/skill-creator`.
- **End-of-session** (`skill_auto_drafter.py`) — fires when the session ends. Auto-generates a draft skill saved to `~/.claude/skills/draft/`, ready to review with `/review-drafts`.

## How It Works

### Mid-session nudge (new)

1. **MCP tool call completes** → PostToolUse hook fires `skill_pattern_watcher.py`
2. **Pattern detected** → same 3-gate filter (see below)
3. **Two signal types**:
   - **SKILL GAP** — existing skill covers this domain but you're doing it manually → suggests improving the skill
   - **NEW SKILL** — no matching skill exists → suggests creating one
4. **Fires once per session** (deduped via `/tmp` flag) — no spam
5. **You run** `/skill-creator` immediately, while the workflow is fresh

### End-of-session draft

1. **Session ends** → Stop hook reads the JSONL transcript via `skill_auto_drafter.py`
2. **Pattern detected** → draft saved to `~/.claude/skills/draft/<name>.md`
3. **Next session** → SessionStart notifies you of pending drafts
4. **You review** → run `/review-drafts` to activate, keep, or discard

## Install

### Step 1 — Add the plugin

Add this to your `~/.claude/settings.json` under `extraKnownMarketplaces`:

```json
"skill-crystallizer": {
  "source": {
    "source": "github",
    "repo": "YOUR_GITHUB_USERNAME/skill-crystallizer"
  }
}
```

Then install via Claude Code: `/plugins install skill-crystallizer@skill-crystallizer`

### Step 2 — Add the PostToolUse hook (mid-session nudge)

Add this to the `hooks.PostToolUse` array in `~/.claude/settings.json`:

```json
{
  "matcher": "mcp__",
  "hooks": [
    {
      "type": "command",
      "command": "PLUGIN_DIR=$(python3 -c \"import pathlib; print(list(pathlib.Path.home().glob('.claude/plugins/cache/skill-crystallizer/skill-crystallizer/*/scripts'))[0])\"); python3 \"$PLUGIN_DIR/skill_pattern_watcher.py\" 2>/dev/null || true"
    }
  ]
}
```

### Step 3 — Add the Stop hook (end-of-session draft)

Add this to the `hooks.Stop` array in `~/.claude/settings.json`:

```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "PAYLOAD=$(cat); PLUGIN_DIR=$(python3 -c \"import pathlib; print(list(pathlib.Path.home().glob('.claude/plugins/cache/skill-crystallizer/skill-crystallizer/*/scripts'))[0])\"); echo \"$PAYLOAD\" | python3 \"$PLUGIN_DIR/skill_auto_drafter.py\" 2>/dev/null"
    }
  ]
}
```

### Step 4 — Add the SessionStart hook (optional but recommended)

```json
{
  "matcher": "",
  "hooks": [
    {
      "type": "command",
      "command": "DRAFTS=$(ls ~/.claude/skills/draft/*.md 2>/dev/null | wc -l | tr -d ' '); if [ \"$DRAFTS\" -gt 0 ]; then echo \"DRAFT SKILLS PENDING: $DRAFTS draft skill(s) waiting — run /review-drafts to review.\"; fi"
    }
  ]
}
```

## Included Skills

| Skill | Command | Description |
|---|---|---|
| review-drafts | `/review-drafts` | Review, activate, keep, or delete auto-generated drafts |

## Pattern Detection Logic

Both scripts share the same 3-gate filter:

| Gate | Constant | What it filters |
|---|---|---|
| 1 | `MIN_MEANINGFUL = 5` | Sessions too short to have a real pattern |
| 2 | `MIN_REPEAT = 3` | One-off tool usage |
| 3 | `MIN_DENSITY = 0.25` | Incidental repeats in long exploratory sessions |

Generic tools (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Agent`) are excluded — only domain-specific tools count.

## Tuning

Edit constants in either script to tune sensitivity:

```python
MIN_REPEAT     = 3     # lower → more drafts
MIN_MEANINGFUL = 5     # lower → fires on shorter sessions
MIN_DENSITY    = 0.25  # lower → less strict on focus
```

## Requirements:

- Claude Code with hooks support
- Python 3 (standard library only — no pip install needed)

## License

MIT
