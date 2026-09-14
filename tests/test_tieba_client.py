from src.tieba_client import TiebaClient, _payload_has_author


def test_signature_is_stable() -> None:
    first = TiebaClient.signature({"b": "2", "a": "1"})
    second = TiebaClient.signature({"a": "1", "b": "2"})
    assert first == second
    assert len(first) == 32


def test_author_detection() -> None:
    payload = {
        "user_list": [{"id": "42", "name": "ExampleUser", "name_show": "显示名"}],
        "post_list": [{"id": "100", "author_id": "42"}],
    }
    assert _payload_has_author(payload, "exampleuser")
    assert _payload_has_author(payload, "显示名")
    assert not _payload_has_author(payload, "someone-else")


def test_author_detection_prefers_numeric_user_id() -> None:
    payload = {
        "user_list": [{"id": "42", "name_show": "贴吧用户_已改名"}],
        "post_list": [{"id": "100", "author_id": 42}],
    }
    assert _payload_has_author(payload, "已经不存在的旧昵称", "42")


def test_author_detection_supports_nested_author_id() -> None:
    payload = {
        "user_list": [],
        "post_list": [{"id": "100", "author": {"user_id": 42}}],
    }
    assert _payload_has_author(payload, "任意昵称", "42")


def test_get_current_user_id(monkeypatch) -> None:
    client = TiebaClient("test", "hifi交易")
    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: {"data": {"user_id": 42, "user_name": "旧昵称"}},
    )
    assert client.get_current_user_id() == "42"


def test_get_current_user_id_falls_back_to_second_endpoint(monkeypatch) -> None:
    client = TiebaClient("test", "hifi交易")
    responses = iter(
        [
            {"no": 110000, "error": "user not login", "data": {}},
            {"data": {"user_id": 42}},
        ]
    )
    monkeypatch.setattr(client, "_json_request", lambda *args, **kwargs: next(responses))
    assert client.get_current_user_id() == "42"


def test_thread_list_uses_nested_pagination_and_sorts_newest_first(monkeypatch) -> None:
    client = TiebaClient("test", "hifi交易")
    sent_data = []
    pages = iter(
        [
            {
                "error_code": "0",
                "thread_list": [
                    {"tid": "1", "title": "old", "create_time": 100, "is_top": "0"},
                    {"tid": "999", "title": "top", "create_time": 999, "is_top": "1"},
                ],
                "page": {"has_more": 1},
            },
            {
                "error_code": "0",
                "thread_list": [
                    {"tid": "2", "title": "new", "create_time": 200, "is_top": "0"},
                    {"tid": "1", "title": "duplicate", "create_time": 100, "is_top": "0"},
                ],
                "page": {"has_more": 0},
            },
        ]
    )
    def fake_request(*args, **kwargs):
        sent_data.append(kwargs["data"])
        return next(pages)

    monkeypatch.setattr(client, "_json_request", fake_request)

    threads = client.list_threads(limit=3)

    assert [thread.tid for thread in threads] == ["2", "1"]
    assert all(data["sort_type"] == "1" for data in sent_data)
    assert all("q_type" not in data for data in sent_data)


def test_reply_accepts_numeric_zero_success(monkeypatch) -> None:
    client = TiebaClient("test", "hifi交易")
    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: {"no": 0, "error": 0, "data": {}},
    )
    client.reply("123", "456", "bd", "test-tbs")


def test_reply_accepts_string_zero_success(monkeypatch) -> None:
    client = TiebaClient("test", "hifi交易")
    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *args, **kwargs: {"no": "0", "error": "0", "data": {}},
    )
    client.reply("123", "456", "bd", "test-tbs")
