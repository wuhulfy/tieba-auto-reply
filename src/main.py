from __future__ import annotations

import logging
import os
import random
import sys
import time
from datetime import datetime

from .config import Config
from .schedule import BEIJING, is_active_schedule, rotation_group
from .state import ReplyState
from .tieba_client import AuthenticationError, RiskControlError, TiebaClient, TiebaError

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run() -> int:
    now = datetime.now(BEIJING)
    schedule_expr = os.getenv("SCHEDULE_EXPR", "").strip()
    if not is_active_schedule(schedule_expr, now):
        logger.info("今日轮换组为 %s，本候选时间不执行", rotation_group(now.date()))
        return 0

    try:
        config = Config.from_env()
    except (ValueError, TypeError) as exc:
        logger.error("配置错误: %s", exc)
        return 2

    if not config.dry_run and not 6 <= now.hour <= 23:
        logger.error("真实回复只允许在北京时间 06:00–23:59 执行")
        return 2

    logger.info(
        "吧=%s，昵称=%s，模式=%s，单次上限=%d",
        config.forum,
        config.username,
        "预演" if config.dry_run else "真实回复",
        config.max_replies,
    )
    state = ReplyState.load(config.state_file)
    client = TiebaClient(config.bduss, config.forum)

    try:
        client.get_tbs()  # fail fast when the credential is invalid
        current_user_id = config.user_id or client.get_current_user_id()
        logger.info(
            "已启用数字用户 ID 查重（%s）",
            "配置值" if config.user_id else "自动获取",
        )
        threads = client.list_threads(config.scan_limit)
    except (AuthenticationError, TiebaError) as exc:
        logger.error("%s", exc)
        return 1

    cutoff = int(now.timestamp()) - config.max_thread_age_hours * 3600
    recent_threads = [thread for thread in threads if thread.created_at >= cutoff]
    candidates = [thread for thread in recent_threads if not state.contains(thread.tid)]
    logger.info(
        "最近 %d 小时内有 %d 个普通主题，去除本地已处理后剩余 %d 个",
        config.max_thread_age_hours,
        len(recent_threads),
        len(candidates),
    )
    if not candidates:
        logger.info("没有需要处理的新帖")
        return 0

    if config.dry_run:
        unanswered = 0
        for thread in candidates:
            if unanswered >= config.max_replies:
                break
            try:
                if client.thread_has_reply_from(
                    thread.tid, config.username, current_user_id
                ):
                    logger.info("[已回复-跳过] tid=%s title=%s", thread.tid, thread.title[:80])
                    state.mark(thread.tid)
                    continue
                unanswered += 1
                logger.info("[预演-未回复] tid=%s title=%s", thread.tid, thread.title[:80])
            except TiebaError as exc:
                logger.error("tid=%s: %s；预演检查停止", thread.tid, exc)
                return 1
        logger.info(
            "预演完成，找到 %d 个未回复帖子，未发送任何回复",
            unanswered,
        )
        return 0

    try:
        fid = client.get_forum_id()
        tbs = client.get_tbs()
    except (AuthenticationError, TiebaError) as exc:
        logger.error("%s", exc)
        return 1

    success = 0
    for thread in candidates:
        if success >= config.max_replies:
            break
        try:
            if client.thread_has_reply_from(thread.tid, config.username, current_user_id):
                logger.info("已检测到本账号回复，跳过 tid=%s", thread.tid)
                state.mark(thread.tid)
                continue

            client.reply(thread.tid, fid, config.reply_content, tbs)
            state.mark(thread.tid)
            success += 1
            logger.info("回复成功 tid=%s title=%s", thread.tid, thread.title[:60])
            if success < config.max_replies:
                time.sleep(random.uniform(config.delay_min, config.delay_max))
        except (RiskControlError, AuthenticationError) as exc:
            logger.error("%s；当次任务立即停止", exc)
            break
        except TiebaError as exc:
            logger.error("tid=%s: %s；当次任务停止", thread.tid, exc)
            break

    logger.info("当次完成：成功回复 %d 帖", success)
    return 0


if __name__ == "__main__":
    sys.exit(run())
