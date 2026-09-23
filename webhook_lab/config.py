import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    database: Path
    admin_token: str
    targets: dict[str, str] = field(default_factory=dict)
    max_body_bytes: int = 262_144
    max_events: int = 5_000

    def __post_init__(self):
        if len(self.admin_token) < 24:
            raise ValueError("WLAB_ADMIN_TOKEN must contain at least 24 characters")
        for name, url in self.targets.items():
            if not name or name.startswith("demo-"):
                raise ValueError("Target names must be nonempty and cannot start with demo-")
            parsed = urlsplit(url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.fragment
                or parsed.query
            ):
                raise ValueError(
                    "Targets require an HTTP(S) URL without credentials/query/fragment"
                )

    @classmethod
    def from_env(cls):
        data = Path(os.getenv("WLAB_DATA_DIR", "data"))
        data.mkdir(parents=True, exist_ok=True)
        token = os.getenv("WLAB_ADMIN_TOKEN")
        if not token:
            token_path = data / "admin.token"
            try:
                with token_path.open("x", encoding="utf-8") as handle:
                    handle.write(secrets.token_urlsafe(32))
                token_path.chmod(0o600)
            except FileExistsError:
                pass
            token = token_path.read_text(encoding="utf-8").strip()
        targets = json.loads(os.getenv("WLAB_TARGETS") or "{}")
        if not isinstance(targets, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in targets.items()
        ):
            raise ValueError("WLAB_TARGETS must be a JSON object mapping names to URLs")
        return cls(database=data / "lab.sqlite3", admin_token=token, targets=targets)
