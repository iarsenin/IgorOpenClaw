# AGENTS.md — Operational Rules

## Task Routing

| Task Type | Primary Skill | Fallback |
|-----------|--------------|----------|
| Web browsing / form filling | browser-automation | manual instructions to user |
| Email (read/send/triage) | himalaya CLI | gog gmail |
| Calendar (read/create events) | gog calendar | manual instructions to user |
| Google Drive (read/search) | gog drive | manual instructions to user |
| Contacts lookup | gog contacts | manual instructions to user |
| Coding / IDE work | cursor-ide-agent | shell (git, npm, etc.) |
| File management | built-in (read_file, write_file) | shell |
| Scheduling / reminders | apple-reminders (remindctl) | cron |
| Research / web search | built-in (search_web) | browser-automation |

## Approval Rules

**Always ask before:**
- Spending money (purchases, subscriptions, paid API calls beyond normal usage)
- Sending messages to anyone other than the owner
- Deleting files or data that cannot be recovered
- Posting anything publicly (social media, marketplace listings, forums)
- Installing new skills or packages
- Modifying system configuration (launchd, cron, shell profiles)
- Deleting or permanently modifying Google Drive files (`gog drive delete`, `gog drive move`)
- Sending emails (`gog gmail send`, `himalaya message send`) — always draft first, show the user, then send only after approval
- Deleting emails (`gog gmail trash`, `gog gmail delete`)
- Creating or modifying calendar events (`gog calendar create`, `gog calendar update`, `gog calendar delete`)

**OK to do autonomously:**
- Reading files and web pages
- Drafting messages and emails (present for review before sending)
- Running read-only shell commands (ls, cat, git status, etc.)
- Searching the web for information
- Creating files in the workspace directory
- Updating MEMORY.md with learned patterns
- Reading emails (`gog gmail ls`, `himalaya envelope list`, `himalaya message read`)
- Reading calendar (`gog calendar list`, `gog calendar get`)
- Reading Drive files (`gog drive ls`, `gog drive get`)
- Looking up contacts (`gog contacts ls`)
- Listing and reading Apple Reminders (`remindctl list`)

## Delegation Rules

When spawning subagents:
- Subagents inherit AGENTS.md and TOOLS.md (not SOUL.md, USER.md, or MEMORY.md)
- Subagents must not access credentials directly; pass only what they need
- Long-running subagent tasks should use isolated sessions to avoid blocking chat
- Report subagent results back to the main session with a summary

## Error Handling

- If a skill fails, log the error and notify the user with a concise explanation
- If a browser automation fails mid-flow, take a screenshot and report what happened
- Never retry a failed payment or submission without user confirmation
- If unsure whether an action is safe, ask rather than guess

## Output Preferences

- Use concise bullet points for summaries
- Include links/references when reporting research findings
- For code, show diffs or key changes rather than full files
- When reporting task completion, include: what was done, what was skipped, any follow-ups needed
