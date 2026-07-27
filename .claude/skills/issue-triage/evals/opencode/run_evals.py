#!/usr/bin/env python3
"""Run the issue-triage evals through the opencode harness.

One disposable git worktree per run, one generated opencode config per run
(the edit deny-list has to name the worktree path), so a with_skill and a
without_skill arm can run concurrently without sharing a tree.

Usage:
    python run_evals.py --cases 1              # smoke test
    python run_evals.py                        # all six, both arms
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path("/Users/marcs/src/redbeat")
SKILL = REPO / ".claude/skills/issue-triage"
SCRATCH = Path(__file__).resolve().parent
WT_ROOT = SCRATCH / "wt"
OUT_ROOT = SCRATCH / "runs"
MODEL = "opencode/big-pickle"
VARIANT = "high"

# gh subcommands that mutate. `gh api` is denied wholesale: it can POST, and no
# glob distinguishes a read from a write reliably enough to bet the repo on.
GH_WRITES = [
    "issue close", "issue edit", "issue comment", "issue create", "issue delete",
    "issue lock", "issue unlock", "issue reopen", "issue pin", "issue unpin",
    "issue transfer", "issue develop",
    "pr create", "pr close", "pr merge", "pr comment", "pr edit", "pr review",
    "pr ready", "pr reopen", "pr lock", "pr checkout",
    "label", "release", "repo", "secret", "variable", "workflow", "cache",
    "gist", "auth", "api",
]

GIT_WRITES = [
    "push", "commit", "tag", "reset", "rebase", "merge", "clean", "stash",
    "checkout -b", "switch -c", "branch -d", "branch -D", "branch -m",
    "remote", "config", "worktree", "am", "cherry-pick", "revert", "gc",
    "update-ref", "filter-branch", "notes",
]


def build_config(worktree: Path) -> dict:
    bash = {"*": "allow"}
    for sub in GIT_WRITES:
        bash[f"git {sub}*"] = "deny"
        bash[f"git -C * {sub}*"] = "deny"
    for sub in GH_WRITES:
        bash[f"gh {sub}*"] = "deny"
    bash["curl*"] = "deny"
    bash["wget*"] = "deny"
    bash["sudo*"] = "deny"
    bash["rm -rf*"] = "deny"
    # Last match wins, so the real-repo deny goes after the allows.
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "*": "allow",
            # Denied so a fixture the run cannot find fails loudly instead of
            # being quietly replaced by the live GitHub thread. No with_skill
            # run used webfetch, so this costs nothing they were relying on.
            "webfetch": "deny",
            "bash": bash,
            "edit": {
                "*": "allow",
                f"{REPO}/**": "deny",
                f"{worktree}/**": "allow",
            },
        },
    }


def prompt_for(case: dict, arm: str, worktree: Path) -> str:
    """Rewrite the Claude Code prompt for opencode.

    Two changes, both recorded in the results file: the slash command becomes a
    skill-tool instruction (opencode resolves commands from .opencode/command/,
    not from skills), and fixture paths are made absolute.

    The paths have to be absolute. With `evals/fixtures/...` relative, case 1's
    baseline resolved it against $HOME, found nothing, and fell back to
    webfetching the live issue #307 -- reading the thread as it stands today
    instead of the frozen report, which is the exact failure the fixtures exist
    to prevent. A relative path that silently resolves somewhere else is worse
    than a missing file, because the run continues and looks fine.
    """
    body = case["prompt"]
    body = body.replace("evals/fixtures/", f"{worktree}/.claude/skills/issue-triage/evals/fixtures/")

    m = re.match(r"/issue-triage(?:\s+(\d+))?\s+--dry-run\.\s*", body)
    rest = body[m.end():] if m else body
    number = m.group(1) if m else None

    if arm == "with_skill":
        head = "Load the issue-triage skill with the skill tool, then follow it to triage "
        head += f"issue {number}" if number else "the issue backlog"
        head += ", with --dry-run (take no write action)."
    else:
        head = "You are triaging the sibson/redbeat GitHub issue backlog as a maintainer. "
        head += f"Triage issue {number}." if number else (
            "Pick a batch of the least-recently-updated open issues that have not yet "
            "been triaged, and report on them."
        )
        head += (
            " This is a dry run: do the full investigation, print your triage report and "
            "the exact comment you would post, but take no write action of any kind."
        )
    return f"{head} {rest}".strip()


def run_one(case: dict, arm: str) -> dict:
    name = case["name"]
    tag = f"case{case['id']}-{arm}"
    wt = WT_ROOT / tag
    out = OUT_ROOT / name / arm
    out.mkdir(parents=True, exist_ok=True)

    if wt.exists():
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(wt)],
                       capture_output=True)
        shutil.rmtree(wt, ignore_errors=True)
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "--detach", str(wt), "HEAD"],
                   check=True, capture_output=True)

    if arm == "without_skill":
        # Drop SKILL.md and references so discovery finds nothing; keep evals/
        # because the fixtures the prompt points at live under it.
        (wt / ".claude/skills/issue-triage/SKILL.md").unlink()
        shutil.rmtree(wt / ".claude/skills/issue-triage/references", ignore_errors=True)

    cfg = out / "opencode.json"
    cfg.write_text(json.dumps(build_config(wt), indent=2))

    prompt = prompt_for(case, arm, wt)
    (out / "prompt.txt").write_text(prompt)

    # Fail before spending a run if a path in the prompt doesn't exist -- the
    # whole point of the absolute rewrite is that a miss must not be silent.
    for token in prompt.split():
        cand = token.rstrip(".,;—").strip("`")
        # Case 6 names a template, `issue-<N>.json`, not a file -- the run picks
        # its own issues. Skip anything with a placeholder in it.
        if "<" in cand:
            continue
        if cand.startswith(str(wt)) and not Path(cand).exists():
            raise FileNotFoundError(f"{tag}: prompt references missing {cand}")

    env = {**os.environ, "OPENCODE_CONFIG": str(cfg)}
    cmd = [
        "opencode", "run", "-m", MODEL, "--variant", VARIANT,
        "--format", "json", "--auto", "--dir", str(wt),
        "--title", f"eval-{tag}", prompt,
    ]

    # The provider drops requests under concurrency with a 401 "No provider
    # available", which it flags isRetryable:false -- but it is transient, and a
    # run that dies in one second is not a result. Retry with backoff rather
    # than recording an empty run as a failure of the model.
    started = time.time()
    for attempt in range(1, 6):
        proc = subprocess.run(cmd, cwd=str(wt), env=env, capture_output=True, text=True)
        if proc.returncode == 0 or "No provider available" not in proc.stdout:
            break
        wait = 20 * attempt
        print(f"retry {tag} in {wait}s (attempt {attempt} hit no-provider)", flush=True)
        time.sleep(wait)
    elapsed = int((time.time() - started) * 1000)

    (out / "events.json").write_text(proc.stdout)
    (out / "stderr.txt").write_text(proc.stderr)

    session_id = None
    for line in proc.stdout.splitlines():
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        for key in ("sessionID", "sessionId", "id"):
            val = evt.get(key) or (evt.get("info") or {}).get(key)
            if isinstance(val, str) and val.startswith("ses_"):
                session_id = val
                break
        if session_id:
            break

    if session_id:
        exported = subprocess.run(["opencode", "export", session_id],
                                  capture_output=True, text=True)
        (out / "transcript.json").write_text(exported.stdout)

    meta = {
        "eval_id": case["id"], "eval_name": name, "arm": arm,
        "model": MODEL, "variant": VARIANT, "session_id": session_id,
        "duration_ms": elapsed, "exit_code": proc.returncode,
        "worktree": str(wt),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"done {tag} exit={proc.returncode} {elapsed//1000}s session={session_id}", flush=True)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="", help="comma-separated eval ids; default all")
    ap.add_argument("--arms", default="with_skill,without_skill")
    ap.add_argument("--jobs", type=int, default=3)
    args = ap.parse_args()

    evals = json.loads((SKILL / "evals/evals.json").read_text())["evals"]
    if args.cases:
        wanted = {int(x) for x in args.cases.split(",")}
        evals = [e for e in evals if e["id"] in wanted]

    jobs = [(c, arm) for c in evals for arm in args.arms.split(",")]
    print(f"{len(jobs)} runs, {args.jobs} at a time, model={MODEL} variant={VARIANT}", flush=True)

    def guarded(job):
        try:
            return run_one(*job)
        except Exception as exc:  # one bad case must not sink the other eleven
            print(f"ERROR {job[0]['name']}/{job[1]}: {exc}", flush=True)
            return {"eval_name": job[0]["name"], "arm": job[1], "error": str(exc)}

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(guarded, jobs))

    (OUT_ROOT / "index.json").write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT_ROOT / 'index.json'}")


if __name__ == "__main__":
    main()
