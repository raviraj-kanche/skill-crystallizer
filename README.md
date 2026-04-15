# skill-crystallizer

> Stop explaining your workflows every time you start a new Claude session.

`skill-crystallizer` is a Claude Code plugin that automatically detects repeating tool patterns at session end and generates draft skills — ready to review and activate with `/review-drafts`.

## How It Works

1. **Session ends** → Stop hook reads the JSONL transcript
2. **Pattern detected** → 3-gate filter catches real workflows, not noise:
   - A non-generic tool appears 3+ times (`MIN_REPEAT`)
   - At least 5 meaningful tool calls in the session (`MIN_MEANINGFUL`)
   - The top tool is ≥25% of all meaningful calls (`MIN_DENSITY`)
3. **Draft generated** → saved to `~/.claude/skills/draft/<name>.md`
4. **Next session** → SessionStart notifies you of pending drafts
5. **You review** → run `/review-drafts` to activate, keep, or discard

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

### Step 2 — Add the Stop hook

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

### Step 3 — Add the SessionStart hook (optional but recommended)

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

`skill_auto_drafter.py` reads the session JSONL transcript and applies 3 gates:

| Gate | Constant | What it filters |
|---|---|---|
| 1 | `MIN_MEANINGFUL = 5` | Sessions too short to have a real pattern |
| 2 | `MIN_REPEAT = 3` | One-off tool usage |
| 3 | `MIN_DENSITY = 0.25` | Incidental repeats in long exploratory sessions |

Generic tools (`Bash`, `Read`, `Write`, `Edit`, `Glob`, `Grep`, `Agent`) are excluded — only domain-specific tools count.

## Tuning

Edit `scripts/skill_auto_drafter.py` constants to tune sensitivity:

```python
MIN_REPEAT     = 3     # lower → more drafts
MIN_MEANINGFUL = 5     # lower → fires on shorter sessions
MIN_DENSITY    = 0.25  # lower → less strict on focus
```

## Requirements

- Claude Code with hooks support
- Python 3 (standard library only — no pip install needed)

## License

MIT
