# Release Process

Always release from the `main` branch using the make target, which ensures tests pass before tagging:

    make release

Version is auto-detected from the "(unreleased)" heading at the top of CHANGES.txt.
Pass `VERSION='M.m.p'` to override.
