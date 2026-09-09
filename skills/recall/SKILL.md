---
name: recall
description: Search and review past pi conversations in ~/.pi/agent/sessions/. Use when the user asks what was discussed, decided, or tried before — "what did we do about X", "find the session where...", "when did we run Y", "look at our history".
---

# Recall

Past conversations are JSONL files, one per session:

```
~/.pi/agent/sessions/--<cwd-with-dashes>--/<timestamp>_<uuid>.jsonl
```

Each line is one entry; `message` entries carry the conversation (roles: user, assistant, toolResult, bashExecution). Lines can be hundreds of KB — never grep-and-read raw; render with `show.py` instead.

`show.py` (next to this file) parses and renders only. Finding things is grep's job:

## Find sessions

```bash
rg -il 'pattern' ~/.pi/agent/sessions/                 # everywhere, case-insensitive
rg -il 'pattern' ~/.pi/agent/sessions/-${PWD//\//-}--/   # one project: sessions from this cwd

# rank sessions by hits (pathfinder trick):
rg -ci 'webview' ~/.pi/agent/sessions/--proj--/*.jsonl | sort -t: -k2 -rn | head

# multi-term vote (order_safety trick): files matching most terms first
for t in webview plan koog; do rg -il "$t" ~/.pi/agent/sessions/; done | sort | uniq -c | sort -rn | head
```

## List sessions

```bash
show.py --titles                    # this project, newest first
show.py --titles ~/Projects/pathfinder -n 10
show.py --titles all -n 10          # across all projects
```

## Read a session

```bash
show.py FILE                        # dialogue: user/assistant text + tool calls
show.py FILE | rg ' user '          # digest: what the human asked, when
show.py FILE --full                 # + tool results and bash output
show.py FILE | rg -C2 'pattern'     # context search within a session
```

## From grep hit to readable context

`rg` on a file finds lines; render exactly those lines (lossless — includes toolResults and thinking, which the dialogue view omits):

```bash
rg -in 'drop schema' FILE | show.py FILE -     # pipe rg -n output
show.py FILE 25,30-40                           # or by line number
```

## Typical flows

- *"When/where did we do X?"* → `rg -il 'X' ~/.pi/agent/sessions/` → `rg -in 'X' FILE | show.py FILE -`
- *"What did we decide about X?"* → find sessions → `show.py FILE | rg ' user '` to skim asks → `show.py FILE` for the dialogue around the decision
- *"Look at our last session"* → `show.py --titles -n 3` → `show.py` newest

Notes: timestamps render in local time; filenames are UTC. `--titles` shows each session's first real user message. The many `--*-.pi-worktrees-*` dirs are subagent sessions.
