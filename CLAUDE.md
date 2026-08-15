# Conventions

Tests are stdlib `unittest`, not pytest -- the `[tool:pytest]` stub in
`setup.cfg` is vestigial and pytest is not installed. Run them with `make test`
(`python -m unittest discover tests`); no live Redis is needed, `fakeredis`
covers it.

Two harness conventions in `tests/basecase.py` are easy to get wrong, and both
fail silently rather than loudly:

- Test classes take a lowercase `test_` prefix (`test_RedBeatEntry`), an old
  celery convention. A `TestThing` class is not collected.
- Subclasses override `setup()`, not `setUp()` -- `AppCase.setUp` builds the
  celery test app and then calls `self.setup()`.

`make lint` runs flake8 with the black and isort plugins: line length 100,
single quotes (`skip-string-normalization`), isort `profile = hug`. CI enforces
it, so run it before pushing.

Every user-visible fix gets a `CHANGES.txt` entry under the `(unreleased)`
heading, in the form `- bugfix, <description>, fixes #NNN`.

Tests live in topical files -- `test_entry.py`, `test_scheduler.py`,
`test_json.py`, `test_schedules.py`, `test_config.py`. A `tests/test_issue_NNN.py`
is a triage artifact, not a permanent home: it exists so an open issue has a
runnable reproduction attached to it. When you fix the underlying bug, move the
test into the topical file, drop its `@unittest.expectedFailure` marker, and
rename it for the behaviour it checks rather than the issue number. Organising
tests by issue number ages badly -- the number stops mattering the moment the
bug is fixed.

# Comments

Default to no comments. Add one only when the WHY is non-obvious: a hidden
constraint, a subtle invariant, a workaround for a specific bug, behaviour
that would surprise a reader. Don't explain WHAT the code does -- well-named
identifiers already do that. Don't reference the current task, fix, or
callers ("used by X", "added for the Y flow", "handles the case from issue
#123") -- that belongs in the commit message, not the code.

# Release Process

Version is derived from git tags via pbr, not stored in any file. Always
release from the `main` branch using the make target, which ensures tests
pass before tagging:

    make release

By default this releases the next patch version. For a minor/major release,
first tag the target version so pbr picks it up (this is the one deliberate
human decision in the process -- pbr can only auto-advance the patch number
on its own):

    make bump-version VERSION='M.m.p'
    make release
