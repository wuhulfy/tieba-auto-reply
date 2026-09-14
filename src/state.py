from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ReplyState:
    path: Path
    processed: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ReplyState":
        if not path.exists():
            return cls(path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("processed", {})
            if not isinstance(values, dict):
                raise ValueError("processed 必须是对象")
            return cls(path=path, processed={str(k): str(v) for k, v in values.items()})
        except (OSError, ValueError, json.JSONDecodeError):
            # A missing/corrupt cache must never be trusted for deduplication.
            return cls(path=path)

    def contains(self, tid: str) -> bool:
        return str(tid) in self.processed

    def mark(self, tid: str) -> None:
        self.processed[str(tid)] = datetime.now(timezone.utc).isoformat()
        if len(self.processed) > 5000:
            newest = sorted(self.processed.items(), key=lambda item: item[1], reverse=True)[:4000]
            self.processed = dict(newest)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"processed": self.processed}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

