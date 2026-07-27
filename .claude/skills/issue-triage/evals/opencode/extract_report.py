#!/usr/bin/env python3
"""Write each run's assistant text out as report.md for grading.

Keeps every text part, not just the last: opencode emits the report in several
parts when the run is long, and the tail alone loses the outcome line on the
batch case.
"""

import json
import sys
from pathlib import Path


def main(paths):
    for p in map(Path, paths):
        chunks = []
        for line in p.read_text().splitlines():
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            part = evt.get("part") or (evt.get("properties") or {}).get("part") or {}
            if part.get("type") == "text" and part.get("text"):
                chunks.append(part["text"])
        out = p.with_name("report.md")
        out.write_text("\n\n---\n\n".join(chunks))
        print(f"{p.parent.parent.name}/{p.parent.name}: {len(chunks)} parts, {len(out.read_text())} chars")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
