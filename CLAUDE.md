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
