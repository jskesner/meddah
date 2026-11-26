"""Module execution support for `python -m app.cli`."""

from __future__ import annotations

from app.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
