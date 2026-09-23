# Contributing

Start with the local demo in the README. Development dependencies are pinned in `requirements-dev.lock`.

Before proposing a change, run `python -m pytest -q`, `python -m ruff check .` and `python -m ruff format --check .`.

For a bug, include the operating system, Python version, exact steps, expected behavior and a synthetic event. Never attach real tokens, inbox URLs, payloads or credentials.

Keep pull requests focused. Explain the problem, resulting behavior and how you tested it. Add a regression test for behavior changes involving capture, persistence, auth or delivery. Architecture proposals should identify a user need before introducing infrastructure.
