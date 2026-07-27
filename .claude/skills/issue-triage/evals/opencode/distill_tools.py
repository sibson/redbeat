#!/usr/bin/env python3
"""Distil an opencode events stream into the tool calls it made, and total tokens.

check_no_writes.py scans text, which is the right call for a Claude Code
transcript but wrong for an opencode one: opencode's `skill` tool inlines the
whole of SKILL.md into the conversation, and SKILL.md says "Never call
`issue_write`". Scanning the raw transcript therefore fails every with_skill run
on the skill's own prohibition.

So write out only what the run actually *invoked* -- tool name plus input, never
tool output -- and point the checker at that.

Usage:
    python distill_tools.py runs/<case>/<arm>/events.json
"""

import json
import sys
from pathlib import Path


def parts(events_path):
    for line in Path(events_path).read_text().splitlines():
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        part = evt.get("part") or (evt.get("properties") or {}).get("part") or {}
        if part:
            yield part


def main(paths):
    for p in paths:
        p = Path(p)
        calls, tokens, billable, cost = [], 0, 0, 0.0
        for part in parts(p):
            if part.get("type") == "tool":
                state = part.get("state") or {}
                calls.append({"tool": part.get("tool"), "input": state.get("input")})
            elif part.get("type") == "step-finish":
                tok = part.get("tokens") or {}
                cache = tok.get("cache") or {}
                tokens += tok.get("total", 0)
                # Per-step totals re-count the cached prefix on every step, so a
                # sum of them is not comparable to a Claude Code token count.
                # Track the uncached share separately -- that is what a step
                # actually paid for.
                billable += (tok.get("input", 0) + tok.get("output", 0)
                             + tok.get("reasoning", 0) + cache.get("write", 0))
                cost += part.get("cost") or 0

        out = p.with_name("tools.jsonl")
        out.write_text("".join(json.dumps(c) + "\n" for c in calls))

        summary = p.with_name("usage.json")
        summary.write_text(json.dumps({
            "tool_uses": len(calls),
            "tokens_step_sum": tokens,
            "tokens_uncached": billable,
            "cost_reported": cost,
        }, indent=2))
        print(f"{p.parent.parent.name}/{p.parent.name}: {len(calls)} calls, "
              f"{billable} uncached tokens ({tokens} step-sum), cost {cost} -> {out.name}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
