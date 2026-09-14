from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

SIGN_KEY = "tiebaclient!!!"
TBS_URL = "https://tieba.baidu.com/dc/common/tbs"
FORUM_INFO_URL = "https://tieba.baidu.com/f/commit/share/fnameShareApi"
USER_INFO_URL = "https://tieba.baidu.com/f/user/json_userinfo"
USER_SYNC_URL = "https://tieba.baidu.com/mo/q/sync"
THREAD_LIST_URL = "https://c.tieba.baidu.com/c/f/frs/page"
POST_LIST_URL = "https://c.tieba.baidu.com/c/f/pb/page"
THREAD_URL = "https://tieba.baidu.com/p/{tid}"
REPLY_URL = "https://tieba.baidu.com/f/commit/post/add"


class TiebaError(RuntimeError):
    pass


class AuthenticationError(TiebaError):
    pass


class RiskControlError(TiebaError):
    pass


@dataclass(frozen=True)
class Thread:
    tid: str
    title: str
    created_at: int
    is_top: bool = False


class TiebaClient:
    def __init__(self, bduss: str, forum: str, timeout: int = 15) -> None:
        if not bduss:
            raise ValueError("BDUSS 不能为空")
        self.bduss = bduss
        self.forum = forum
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
        )
        requests.utils.add_dict_to_cookiejar(self.session.cookies, {"BDUSS": bduss})

    @staticmethod
    def signature(data: dict[str, Any]) -> str:
        raw = "".join(f"{key}={data[key]}" for key in sorted(data))
        return hashlib.md5((raw + SIGN_KEY).encode("utf-8")).hexdigest().upper()

    def _json_request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retries: int = 3,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        for attempt in range(retries):
            try:
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout if timeout is None else timeout,
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("响应不是 JSON 对象")
                return payload
            except (requests.RequestException, ValueError) as exc:
                if attempt == retries - 1:
                    raise TiebaError(f"请求失败: {type(exc).__name__}") from exc
                time.sleep(1.5 * (2**attempt) + random.uniform(0, 0.8))
        raise AssertionError("unreachable")

    def get_tbs(self) -> str:
        payload = self._json_request("GET", TBS_URL)
        tbs = str(payload.get("tbs", ""))
        if not tbs or payload.get("is_login") in {0, "0"}:
            raise AuthenticationError("BDUSS 已失效或尚未登录")
        return tbs

    def get_forum_id(self) -> str:
        payload = self._json_request(
            "GET",
            FORUM_INFO_URL,
            params={"ie": "utf-8", "fname": self.forum},
        )
        fid = str(payload.get("data", {}).get("fid", ""))
        if not fid:
            raise TiebaError(f"无法获取吧 ID: {self.forum}")
        return fid

    def get_current_user_id(self) -> str:
        errors: list[str] = []
        for url in (USER_SYNC_URL, USER_INFO_URL):
            try:
                payload = self._json_request(
                    "GET",
                    url,
                    headers={"Referer": "https://tieba.baidu.com/"},
                    retries=1,
                    timeout=min(self.timeout, 8),
                )
                data = payload.get("data", payload)
                if isinstance(data, dict):
                    for key in ("user_id", "uid", "id"):
                        user_id = str(data.get(key) or "").strip()
                        if user_id and user_id != "0":
                            return user_id
                errors.append(str(payload.get("error") or payload.get("error_msg") or "无用户 ID"))
            except TiebaError as exc:
                errors.append(str(exc))
        raise AuthenticationError(
            "无法取得当前登录账号的数字用户 ID: " + "；".join(errors)
        )

    def list_threads(self, limit: int = 100) -> list[Thread]:
        results: dict[str, Thread] = {}
        page = 1
        while len(results) < limit:
            data: dict[str, Any] = {
                "BDUSS": self.bduss,
                "_client_id": "wappc_1534235498291_488",
                "_client_type": "2",
                "_client_version": "9.7.8.0",
                "_phone_imei": "000000000000000",
                "from": "tieba",
                "kw": self.forum,
                "pn": str(page),
                "rn": str(min(100, limit)),
                # Explicitly request creation-time order.  Without this the
                # endpoint returns Tieba's smart/hot mixture.
                "sort_type": "1",
                "with_group": "1",
            }
            data["sign"] = self.signature(data)
            payload = self._json_request("POST", THREAD_LIST_URL, data=data)
            error_code = str(payload.get("error_code", "0"))
            if error_code not in {"", "0"}:
                raise TiebaError(f"获取主题列表失败: {payload.get('error_msg', error_code)}")

            items = payload.get("thread_list", [])
            if not isinstance(items, list) or not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                tid = str(item.get("tid") or item.get("id") or "")
                if not tid:
                    continue
                thread = Thread(
                    tid=tid,
                    title=str(item.get("title") or "(无标题)"),
                    created_at=_to_timestamp(item.get("create_time")),
                    is_top=str(item.get("is_top", "0")) == "1",
                )
                if not thread.is_top:
                    results[tid] = thread
                if len(results) >= limit:
                    break
            page_info = payload.get("page", {})
            has_more = page_info.get("has_more") if isinstance(page_info, dict) else None
            if has_more in {0, "0", False}:
                break
            page += 1
        # Newest first.  The API may repeat pinned or recently bumped threads
        # between pages, so `results` is keyed by tid before sorting.
        return sorted(
            results.values(),
            key=lambda item: (item.created_at, int(item.tid)),
            reverse=True,
        )

    def thread_has_reply_from(
        self,
        tid: str,
        username: str,
        user_id: str,
        tail_pages: int = 3,
    ) -> bool:
        first_page = self._get_post_page(tid, 1)
        if _payload_has_author(first_page, username, user_id):
            return True
        page_info = first_page.get("page", {})
        if not isinstance(page_info, dict):
            page_info = {}
        total_pages = _to_timestamp(
            page_info.get("total_page") or page_info.get("new_total_page") or 1
        )
        total_pages = max(1, total_pages)
        start = max(2, total_pages - tail_pages + 1)
        for page in range(start, total_pages + 1):
            if _payload_has_author(self._get_post_page(tid, page), username, user_id):
                return True
        return False

    def _get_post_page(self, tid: str, page: int) -> dict[str, Any]:
        data: dict[str, Any] = {
            "BDUSS": self.bduss,
            "_client_id": "wappc_1534235498291_488",
            "_client_type": "2",
            "_client_version": "9.7.8.0",
            "_phone_imei": "000000000000000",
            "from": "tieba",
            "kz": tid,
            "pn": str(page),
            "rn": "30",
            "r": "0",
            "lz": "0",
            "st": "0",
            "z": "0",
        }
        data["sign"] = self.signature(data)
        payload = self._json_request("POST", POST_LIST_URL, data=data)
        error_code = str(payload.get("error_code", "0"))
        if error_code not in {"", "0"}:
            message = str(payload.get("error_msg") or error_code)[:200]
            raise TiebaError(f"无法检查帖子 {tid}: {message}")
        return payload

    def reply(self, tid: str, fid: str, content: str, tbs: str) -> None:
        payload = self._json_request(
            "POST",
            REPLY_URL,
            data={
                "ie": "utf-8",
                "kw": self.forum,
                "fid": fid,
                "tid": tid,
                "content": content,
                "is_login": "1",
                "rich_text": "1",
                "tbs": tbs,
                "__type__": "reply",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": THREAD_URL.format(tid=tid),
            },
        )
        error = str(payload.get("error", ""))
        error_code = str(
            payload.get("err_code", payload.get("error_code", payload.get("no", "0")))
        )
        message = _safe_message(payload)
        success_values = {"", "0", "None"}
        if error in success_values and error_code in success_values:
            return
        if _looks_like_risk_control(error_code, message):
            raise RiskControlError(f"贴吧要求验证或触发风控: {message}")
        if "登录" in message or "BDUSS" in message.upper():
            raise AuthenticationError(f"登录失效: {message}")
        raise TiebaError(f"回复失败({error_code}): {message}")


def _to_timestamp(value: Any) -> int:
    if isinstance(value, dict):
        value = value.get("time") or value.get("timestamp") or 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _payload_has_author(
    payload: dict[str, Any], username: str, user_id: str = ""
) -> bool:
    expected_id = str(user_id).strip()
    posts = [post for post in payload.get("post_list", []) if isinstance(post, dict)]
    if expected_id and any(expected_id in _post_author_ids(post) for post in posts):
        return True

    expected = username.casefold()
    author_ids: set[str] = set()
    for user in payload.get("user_list", []):
        if not isinstance(user, dict):
            continue
        names = {str(user.get("name", "")), str(user.get("name_show", ""))}
        if expected in {name.casefold() for name in names if name}:
            author_ids.add(str(user.get("id", "")))
    if not author_ids:
        return False
    return any(_post_author_ids(post) & author_ids for post in posts)


def _post_author_ids(post: dict[str, Any]) -> set[str]:
    values = {str(post.get("author_id") or ""), str(post.get("user_id") or "")}
    author = post.get("author")
    if isinstance(author, dict):
        values.update(
            {
                str(author.get("id") or ""),
                str(author.get("user_id") or ""),
            }
        )
    return {value for value in values if value}


def _safe_message(payload: dict[str, Any]) -> str:
    for key in ("errmsg", "error_msg", "error", "msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
    return "未知错误"


def _looks_like_risk_control(code: str, message: str) -> bool:
    text = f"{code} {message}"
    markers = ("验证码", "安全验证", "操作频繁", "请稍后", "vcode", "captcha")
    return any(marker.casefold() in text.casefold() for marker in markers)
