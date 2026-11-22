import logging
from datetime import datetime
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from config import DIGEST_HOUR, DIGEST_MINUTE, TIMEZONE
from database import (
    get_all_active_events_for_digest,
    get_due_events,
    mark_event_completed,
)

logger = logging.getLogger("scheduler")


def compute_remaining_text(target_dt_iso: str, has_time: bool) -> str:
    try:
        target_dt = datetime.fromisoformat(target_dt_iso)
    except Exception:
        return "не определено"

    now = datetime.now()
    diff = target_dt - now
    if diff.total_seconds() <= 0:
        return "срок наступил"

    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days} д.")
    if hours > 0 or days > 0:
        parts.append(f"{hours} ч.")
    if has_time:
        parts.append(f"{minutes} мин.")

    return " ".join(parts) if parts else "менее минуты"


async def check_due_events(bot: Bot) -> None:
    now_iso = datetime.now().isoformat()
    try:
        due_events = await get_due_events(now_iso)
        for event in due_events:
            event_id = event["id"]
            user_id = event["user_id"]
            title = event["title"]
            target_date = event["target_date"]
            target_time = event["target_time"]
            has_time = bool(event["has_time"])

            time_str = f" {target_time}" if has_time and target_time else ""
            text = (
                "Напоминание. Наступил срок события:\n"
                f"{title}\n"
                f"Цель: {target_date}{time_str}"
            )
            try:
                await bot.send_message(chat_id=user_id, text=text)
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

            await mark_event_completed(event_id)
    except Exception as e:
        logger.error(f"Ошибка при проверке наступивших событий: {e}")


async def send_daily_digest(bot: Bot) -> None:
    try:
        events = await get_all_active_events_for_digest()
        if not events:
            return

        user_events_map = {}
        for event in events:
            user_id = event["user_id"]
            if user_id not in user_events_map:
                user_events_map[user_id] = []
            user_events_map[user_id].append(event)

        for user_id, user_events in user_events_map.items():
            lines = ["Ежедневная сводка напоминаний:\n"]
            for ev in user_events:
                title = ev["title"]
                target_date = ev["target_date"]
                target_time = ev["target_time"]
                has_time = bool(ev["has_time"])
                time_str = f" {target_time}" if has_time and target_time else ""
                remaining = compute_remaining_text(ev["target_datetime"], has_time)

                lines.append(f"- {title}: осталось {remaining} (цель: {target_date}{time_str})")

            lines.append(f"\nВсего активных событий: {len(user_events)}")
            message_text = "\n".join(lines)

            try:
                await bot.send_message(chat_id=user_id, text=message_text)
            except Exception as e:
                logger.warning(f"Не удалось отправить сводку пользователю {user_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при формировании ежедневной сводки: {e}")


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Ежедневная рассылка сводки в заданное время (по умолчанию 10:00)
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE, timezone=tz),
        args=[bot],
        id="daily_digest",
        replace_existing=True
    )

    # Проверка наступивших точных таймеров каждые 30 секунд
    scheduler.add_job(
        check_due_events,
        trigger=IntervalTrigger(seconds=30),
        args=[bot],
        id="check_due_events",
        replace_existing=True
    )

    return scheduler
