# Running the evals through opencode

The suite in `../` is written for Claude Code: you ask Claude to run it, and it
spawns a subagent per arm. This directory runs the same six cases against any
model opencode can reach, which is how the `opencode/big-pickle` record in
`../results/` was produced.

```
python run_evals.py                    # all six cases, both arms
python run_evals.py --cases 1 --jobs 1 # one case, one at a time
```

Then, for every run:

```
python distill_tools.py ../../../../../runs/*/*/events.json
python extract_report.py ../../../../../runs/*/*/events.json
python ../check_no_writes.py <runs>/*/*/tools.jsonl
```

Outputs land under `runs/<case-name>/<arm>/` next to `run_evals.py`.

## Why the prompts are not the ones in evals.json

Two rewrites happen in `prompt_for`, and both are load-bearing.

`/issue-triage 307 --dry-run` invokes nothing under opencode — slash commands
resolve from `.opencode/command/`, not from skills — so it becomes an
instruction to load the skill with the `skill` tool. The baseline arm gets the
same task with no mention of a skill, and its worktree has `SKILL.md` and
`references/` deleted so discovery finds nothing.

Fixture paths become absolute. Left relative, a baseline run resolved
`evals/fixtures/issue-307.json` against `$HOME`, found nothing, and quietly
webfetched the live issue #307 — grading the skill against today's thread
instead of the frozen report, with nothing in the output to say so. `webfetch`
is denied for that reason, and the runner refuses to start a run whose prompt
names a path that does not exist.

Because the prompts differ, results from this harness are not directly
comparable to the Agent-tool records. Record what changed; `results/README.md`
explains which fields have to be pinned.

## The no-writes screen needs a distilled log

`check_no_writes.py` scans text, which is right for a Claude Code transcript and
wrong for an opencode one: the `skill` tool inlines all of `SKILL.md`, and
`SKILL.md` contains the string `issue_write` in the sentence forbidding it. Every
with-skill run therefore fails on the skill's own prohibition.

`distill_tools.py` writes `tools.jsonl` — tool name and input, never tool output
— and the screen passes against that. Point the checker there, not at
`transcript.json`.

## Isolation

Each run gets a throwaway git worktree and a generated `opencode.json` that
denies the write paths: 20 mutating `git` subcommands (in both bare and `git -C`
form), 22 mutating `gh` subcommands, `gh api` wholesale (no glob separates a
read from a POST reliably), `curl`, `wget`, `sudo`, and edits anywhere outside
that run's worktree. `--auto` approves whatever is left, so the deny-list is the
only thing between an unattended run and the live repo — `gh` is normally
authenticated with `repo` scope. Treat the list as the safety boundary it is
when editing it.

## Provider instability

`opencode/big-pickle` returns `No provider available` (HTTP 401, flagged
`isRetryable: false`) under concurrency — 3 of 12 runs died at `--jobs 3`, 5 of
12 at `--jobs 2`. It is transient despite the flag. The runner retries with
backoff; prefer `--jobs 1` for a record you intend to keep.
