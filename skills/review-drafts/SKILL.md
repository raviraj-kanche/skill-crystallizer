# Review Draft Skills

Review auto-generated draft skills in ~/.claude/skills/draft/ and decide what to do with each one.

## Steps

1. List all `.md` files in `~/.claude/skills/draft/` using Glob
2. If none found, tell the user "No draft skills pending" and stop
3. For each draft file found:
   a. Read the file
   b. Show the user: skill name, detected tools, keywords, and the full draft content
   c. Ask the user what to do with this draft using AskUserQuestion:
      - **Activate** — move to `/skill-creator` workflow to refine and register it
      - **Keep as draft** — leave it in draft folder for later
      - **Delete** — remove the file, it's not useful
4. Act on the user's choice immediately before moving to the next draft:
   - Activate → open the file, help user refine the Steps section, then save to `~/.claude/skills/<name>/SKILL.md` and delete the draft
   - Keep → do nothing, move to next draft
   - Delete → delete the file using Bash `rm`
5. After all drafts reviewed, summarize: how many activated, kept, deleted

## Notes
- Never activate a draft without the user reviewing the Steps section first
- If activating: the skill name slug becomes the folder name under `~/.claude/skills/`
- Draft files have `draft: true` in frontmatter — remove it when activating
- Be concise when showing each draft — lead with the detected tool pattern and keywords, not the full boilerplate
