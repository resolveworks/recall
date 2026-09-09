# recall

A pi skill for looking at past conversations in `~/.pi/agent/sessions/`.

One small parser (`skills/recall/show.py`, stdlib-only) renders session JSONL
readably; grep/rg does all the finding. See `skills/recall/SKILL.md`.

## Install

```bash
pi install ~/Projects/recall
```

Local-path installs are referenced in place — edits here are live, no reinstall
needed (except for new files, which need a pi restart to be discovered).
