# Release Process

Always release from the `main` branch using the make target, which ensures tests pass before tagging:

    VERSION='M.m.p' make release
