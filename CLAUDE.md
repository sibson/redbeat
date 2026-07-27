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
