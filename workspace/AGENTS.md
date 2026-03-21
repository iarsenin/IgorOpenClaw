# AGENTS.md — Operational Rules

## Task Routing

| Task Type | Primary Skill | Fallback |
|-----------|--------------|----------|
| Web browsing / form filling | browser-automation | manual instructions to user |
| Email (read/send/triage) | gmail | send-email (SMTP) |
| Coding / IDE work | cursor-ide-agent | shell (git, npm, etc.) |
| File management | built-in (read_file, write_file) | shell |
| Scheduling / reminders | cron | heartbeat |
| Research / web search | built-in (search_web) | browser-automation |

## Approval Rules

**Always ask before:**
- Spending money (purchases, subscriptions, paid API calls beyond normal usage)
- Sending messages to anyone other than the owner
- Deleting files or data that cannot be recovered
- Posting anything publicly (social media, marketplace listings, forums)
- Installing new skills or packages
- Modifying system configuration (launchd, cron, shell profiles)

**OK to do autonomously:**
- Reading files and web pages
- Drafting messages and emails (present for review before sending)
- Running read-only shell commands (ls, cat, git status, etc.)
- Searching the web for information
- Creating files in the workspace directory
- Updating MEMORY.md with learned patterns

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
