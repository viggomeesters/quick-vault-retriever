# Release status

## Current release

Version `0.1.0` establishes the local-first CLI, Raycast adapter, versioned evidence contract,
synthetic verification suite, and professional public repository foundation.

Release artifacts are the source archive and Python source distribution/wheel produced by:

```bash
make check
uv build
```

Maintainers publish only from a clean `main` commit after privacy and secret-history checks pass.
The GitHub release and tag are authoritative; no package registry publication is required for the
initial source-first release.
