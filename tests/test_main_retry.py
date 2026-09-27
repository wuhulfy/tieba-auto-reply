from datetime import datetime

import src.main as main_module
from src.schedule import BEIJING
from src.tieba_client import Thread, TiebaError


FIXED_NOW = datetime(2026, 9, 27, 12, 0, tzinfo=BEIJING)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW if tz is not None else FIXED_NOW.replace(tzinfo=None)


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        self.reply_calls: list[str] = []
        self.outcomes = [TiebaError("first"), None, TiebaError("third"), TiebaError("fourth")]

    def get_tbs(self) -> str:
        return "tbs"

    def get_forum_id(self) -> str:
        return "fid"

    def list_threads(self, limit: int) -> list[Thread]:
        created_at = int(FIXED_NOW.timestamp())
        return [Thread(str(index), f"thread-{index}", created_at - index) for index in range(1, 5)]

    def thread_has_reply_from(self, tid: str, username: str, user_id: str) -> bool:
        return False

    def reply(self, tid: str, fid: str, content: str, tbs: str) -> None:
        self.reply_calls.append(tid)
        outcome = self.outcomes.pop(0)
        if outcome is not None:
            raise outcome


def test_real_run_stops_after_two_consecutive_reply_failures(monkeypatch, tmp_path) -> None:
    client = FakeClient()
    monkeypatch.setattr(main_module, "datetime", FixedDateTime)
    monkeypatch.setattr(main_module, "TiebaClient", lambda *args, **kwargs: client)
    monkeypatch.setattr(main_module.time, "sleep", lambda seconds: None)
    monkeypatch.setenv("BDUSS", "test")
    monkeypatch.setenv("TIEBA_USERNAME", "test-user")
    monkeypatch.setenv("TIEBA_USER_ID", "42")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("MAX_REPLIES", "3")
    monkeypatch.setenv("REPLY_DELAY_MIN", "0")
    monkeypatch.setenv("REPLY_DELAY_MAX", "0")
    monkeypatch.setenv("STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.delenv("SCHEDULE_EXPR", raising=False)

    result = main_module.run()

    assert result == 0
    assert client.reply_calls == ["1", "2", "3", "4"]
    state_text = (tmp_path / "state.json").read_text(encoding="utf-8")
    assert '"2"' in state_text
    assert '"1"' not in state_text
    assert '"3"' not in state_text
    assert '"4"' not in state_text
