from src.config import Config


def test_max_replies_can_exceed_twenty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BDUSS", "test")
    monkeypatch.setenv("TIEBA_USERNAME", "test-user")
    monkeypatch.setenv("MAX_REPLIES", "75")
    monkeypatch.setenv("STATE_FILE", str(tmp_path / "state.json"))

    config = Config.from_env()

    assert config.max_replies == 75
    assert config.delay_min == 5
    assert config.delay_max == 10
