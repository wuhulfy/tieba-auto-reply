from pathlib import Path

from src.state import ReplyState


def test_state_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = ReplyState.load(path)
    state.mark("123")
    restored = ReplyState.load(path)
    assert restored.contains("123")
    assert not restored.contains("456")

