#!/usr/bin/env python3
"""recall — render pi session JSONL readably. Grep does the finding.

  show.py FILE                      dialogue: one line per entry, role-labeled
  show.py FILE --full               also render tool results and bash output
  show.py FILE | rg ' user '        user-message digest
  show.py FILE | rg -C2 'pattern'   context search within a session
  rg -n 'pattern' FILE | show.py FILE -    render the matched lines readably
  show.py FILE 25,30-40             render specific lines (line numbers from rg -n)
  show.py --titles [DIR|PATH|all] [-n N]  list sessions titled by first user msg

Sessions live in ~/.pi/agent/sessions/--<cwd-with-dashes>--/<timestamp>_<uuid>.jsonl
"""
import glob
import json
import os
import re
import sys

SESSIONS = os.path.expanduser("~/.pi/agent/sessions")
ATTACH = re.compile(r'^<file name="([^"]+)"')


def clip(t, limit):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= limit:
        return t
    head = int(limit * 0.7)
    return t[:head].rstrip() + " [...] " + t[-(limit - head - 5):].lstrip()


class Fmt:
    def __init__(self):
        self.prev_day = None

    def ts(self, iso):
        from datetime import datetime
        try:
            d = datetime.fromisoformat((iso or "").replace("Z", "+00:00")).astimezone()
        except ValueError:
            return "??:??"
        day = d.strftime("%m-%d")
        stamp = d.strftime("%H:%M") if day == self.prev_day else d.strftime("%m-%d %H:%M")
        self.prev_day = day
        return stamp


def parts(content):
    """-> (texts, marks, tools, thinking) extracted from a content field."""
    texts, marks, tools, thinking = [], [], [], []
    if isinstance(content, str):
        texts = [content] if content.strip() else []
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                s = b.get("text", "") or ""
                m = ATTACH.match(s.strip())
                if m:
                    marks.append("[file: %s]" % m.group(1))
                elif s.strip():
                    texts.append(s)
            elif t == "thinking":
                thinking.append(b.get("thinking", ""))
            elif t == "toolCall":
                args = b.get("arguments") or {}
                arg = args.get("command") or args.get("path") or next(iter(args.values()), "")
                tools.append("%s: %s" % (b.get("name", "?"), clip(str(arg), 140)))
    return texts, marks, tools, thinking


def read_lines(path):
    with open(path, errors="replace") as f:
        return f.readlines()


def render(path, lines, linenos=None, full=False):
    """Render whole file (linenos=None) or specific 1-based line numbers."""
    fmt = Fmt()
    if linenos is None:
        linenos = range(1, len(lines) + 1)
    for n in linenos:
        if not (1 <= n <= len(lines)):
            continue
        try:
            e = json.loads(lines[n - 1])
        except (json.JSONDecodeError, ValueError):
            print("%6d <unparsable>" % n)
            continue
        t = e.get("type")
        if t == "session":
            continue
        if t == "message":
            m = e.get("message", {})
            role = m.get("role", "?")
            texts, marks, tools, thinking = parts(m.get("content"))
            ts = fmt.ts(e.get("timestamp"))
            verbose = full or linenos is not None
            if role == "toolResult":
                if verbose:
                    print("%s %6d %-9s %s" % (ts, n, "result", clip(" ".join(texts), 1500)))
                continue
            if role == "bashExecution":
                if verbose:
                    print("%s %6d %-9s %s -> exit %s" % (ts, n, "bash!", clip(m.get("command", ""), 300), m.get("exitCode", "?")))
                    if m.get("output"):
                        print("%s %6d %-9s %s" % (ts, n, "output", clip(m.get("output"), 1500)))
                continue
            label = role[:9]
            body = clip(" ".join(texts), 2000 if linenos is None else 6000)
            if marks:
                body = (body + " " if body else "") + " ".join(marks)
            print("%s %6d %-9s %s" % (ts, n, label, body))
            for think in thinking:
                print("%s %6d %-9s %s" % (ts, n, "thinking", clip(think, 2000 if linenos is None else 6000)))
            for tool in tools:
                print("%s %6d %-9s %s" % (ts, n, "tool", tool))
        elif t == "compaction":
            print("%s %6d %-9s [%s tokens summarized] %s" % (fmt.ts(e.get("timestamp")), n, "compact",
                  format(e.get("tokensBefore", 0), ","), clip(e.get("summary", ""), 140)))
        elif t == "branch_summary":
            print("%s %6d %-9s %s" % (fmt.ts(e.get("timestamp")), n, "branch", clip(e.get("summary", ""), 140)))
        # other entry types (model_change, labels, custom, ...) are noise: skip


def print_file(path, linenos, full):
    lines = read_lines(path)
    header = None
    try:
        header = json.loads(lines[0]) if lines and json.loads(lines[0]).get("type") == "session" else None
    except (json.JSONDecodeError, ValueError):
        pass
    fmt = Fmt()
    if header:
        print("# %s" % os.path.basename(path))
        print("# cwd %s   %s lines" % (header.get("cwd", "?"), len(lines)))
    render(path, lines, linenos, full)


def parse_spec(spec):
    """'25,30-40' -> [25, 30..40]"""
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def stdin_linenos():
    """Extract leading line numbers from piped rg/grep -n output.
    Handles both 'N:...' and 'path/file:N:...' forms. Dedupes, keeps order."""
    out = []
    for line in sys.stdin:
        m = re.match(r"^(?:[^:\s]+:)?(\d+):", line)
        if m and int(m.group(1)) not in out:
            out.append(int(m.group(1)))
    return out


def first_user_title(path):
    with open(path, errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if e.get("type") == "message" and e.get("message", {}).get("role") == "user":
                texts, marks, _, _ = parts(e["message"].get("content"))
                if texts:
                    t = clip(" ".join(texts), 100)
                    if marks:
                        t = clip(" ".join(marks) + " " + t, 100)
                    return t
    return "(no user messages)"


def human(n):
    for unit in "KM":
        if n < 1024:
            return "%.1f%s" % (n, unit)
        n /= 1024.0
    return "%.1fM" % n


def print_titles(arg, limit):
    if arg == "all":
        files = sorted(glob.glob(os.path.join(SESSIONS, "*", "*.jsonl")), reverse=True)
    else:
        if not arg:
            arg = os.getcwd()
        d = os.path.abspath(os.path.expanduser(arg))
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*.jsonl")):
            files = glob.glob(os.path.join(d, "*.jsonl"))
        else:
            cand = os.path.join(SESSIONS, "--" + d.lstrip("/").replace("/", "-") + "--")
            if not os.path.isdir(cand):
                sys.exit("No session dir for %s (look in %s)" % (arg, SESSIONS))
            files = glob.glob(os.path.join(cand, "*.jsonl"))
        files = sorted(files, reverse=True)
    for path in files[:limit]:
        stamp = os.path.basename(path)[:16].replace("T", " ")
        print("%s  %5s  %s" % (stamp, human(os.path.getsize(path)), first_user_title(path)))


def main():
    args = sys.argv[1:]
    full = "--full" in args
    args = [a for a in args if a != "--full"]
    if not args:
        sys.exit(__doc__.strip())
    if args[0] == "--titles":
        arg = args[1] if len(args) > 1 and not args[1].startswith("-") else ""
        limit = 25
        if "-n" in args:
            limit = int(args[args.index("-n") + 1])
        print_titles(arg, limit)
        return
    path = args[0]
    spec = args[1] if len(args) > 1 else None
    if spec == "-":
        linenos = stdin_linenos() or None
        print_file(path, linenos, full)
    elif spec:
        print_file(path, parse_spec(spec), full)
    else:
        print_file(path, None, full)


if __name__ == "__main__":
    main()
