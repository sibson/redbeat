#!/usr/bin/env python3
"""Freeze a GitHub issue into an eval fixture.

Evals that read the live API decay in two directions at once. The backlog
moves under them -- a fixed bug turns a "confirmed" expectation into a wrong
one -- and, worse, this skill's own triage comments land in the very threads
the evals read, so a run can score well by reading back an answer a previous
run posted. Neither failure is loud; both just quietly stop measuring
anything.

A fixture is the issue as the reporter filed it. Comments are truncated at a
pinned date, and state/state_reason/labels are dropped so a closed issue
can't announce its own verdict -- the expected outcome belongs in evals.json,
where the grader reads it and the agent doesn't.

Usage:
    <fetch issue JSON>  | python snapshot.py --number 307 --as-of 2026-01-21
    <fetch issue list>  | python snapshot.py --list --as-of 2026-07-27

MCP tools aren't reachable from a script, so Claude does the fetching and
pipes the result here to be normalized. Input is the `get` response, or a
JSON object {"issue": <get>, "comments": [<get_comments>]}.
"""

import argparse
import json
import pathlib
import sys

# Dropped because they leak the answer: an eval that can read state_reason
# "completed" doesn't have to work out whether the bug was real.
VERDICT_FIELDS = ('state', 'state_reason', 'closed_at', 'closed_by', 'labels')

# Kept because triage legitimately uses them -- reported versions live in the
# body, and comment authorship drives the idempotency check.
KEEP_ISSUE = ('number', 'title', 'body', 'user', 'created_at', 'comments')
KEEP_COMMENT = ('user', 'created_at', 'body')


# The batch case needs the backlog it selects from, not one issue's text. Labels
# and updated_at stay: "least-recently-updated, carrying no triage label" is the
# selection rule under test, so stripping them would remove the judgment.
KEEP_LISTED = ('number', 'title', 'user', 'created_at', 'updated_at', 'labels', 'comments')


def prune(obj, keep):
    return {k: obj[k] for k in keep if k in obj}


def build_list(raw, as_of):
    issues = raw.get('issues', raw) if isinstance(raw, dict) else raw
    return {
        '_comment': (
            f'Eval fixture: open-issue backlog frozen as of {as_of or "now"}. '
            'Treat as the authoritative issue list in place of the live API.'
        ),
        'as_of': as_of,
        'issue_count': len(issues),
        'issues': [prune(i, KEEP_LISTED) for i in issues],
    }


def build(raw, number, as_of):
    issue = raw.get('issue', raw)
    comments = raw.get('comments', [])
    if isinstance(comments, dict):
        comments = comments.get('comments', comments.get('data', []))

    kept, dropped = [], 0
    for c in comments:
        # String compare is fine and deliberate: ISO-8601 UTC sorts
        # lexicographically, and avoiding a parse keeps this dependency-free.
        if as_of and c.get('created_at', '') > as_of:
            dropped += 1
            continue
        kept.append(prune(c, KEEP_COMMENT))

    return {
        '_comment': (
            f'Eval fixture for issue #{number}, frozen as of {as_of or "now"}. '
            'Treat this as the authoritative issue content in place of the live '
            'API. Resolution is held out in ground-truth/ -- do not go looking '
            'for it, and do not post any of this anywhere.'
        ),
        'issue_number': number,
        'as_of': as_of,
        'comments_withheld': dropped,
        'issue': prune(issue, KEEP_ISSUE),
        'comments': kept,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--number', type=int, help='single issue; omit with --list')
    p.add_argument('--list', action='store_true', help='freeze an open-issue backlog')
    p.add_argument('--as-of', help='ISO date; comments after it are withheld')
    p.add_argument('--out', help='defaults to fixtures/issue-<number>.json')
    args = p.parse_args()

    if args.list == (args.number is not None):
        print('ERROR  pass exactly one of --number or --list', file=sys.stderr)
        return 2

    try:
        raw = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f'ERROR  stdin is not JSON: {exc}', file=sys.stderr)
        return 2

    if args.list:
        fixture = build_list(raw, args.as_of)
        default = 'fixtures/backlog.json'
        summary = f'{fixture["issue_count"]} issues'
    else:
        fixture = build(raw, args.number, args.as_of)
        leaked = [f for f in VERDICT_FIELDS if f in fixture['issue']]
        if leaked:  # belt and braces -- prune() should already have dropped these
            print(f'ERROR  verdict fields survived: {leaked}', file=sys.stderr)
            return 1
        default = f'fixtures/issue-{args.number}.json'
        summary = (
            f'{len(fixture["comments"])} comments kept, ' f'{fixture["comments_withheld"]} withheld'
        )

    out = pathlib.Path(args.out or default)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, indent=2) + '\n')

    print(f'wrote {out}: {summary}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
