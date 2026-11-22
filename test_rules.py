import asyncio
import os
import re
import sys
from pathlib import Path
import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from api.routes import setup_app
from database import (
    add_or_update_user,
    create_event,
    delete_event,
    get_all_active_events_for_digest,
    get_due_events,
    get_user_events,
    init_db,
    mark_event_completed,
    update_event,
)

EMOJI_PATTERN = re.compile(
    r"[\U0001F600-\U0001F64F"
    r"\U0001F300-\U0001F5FF"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F700-\U0001F77F"
    r"\U0001F780-\U0001F7FF"
    r"\U0001F800-\U0001F8FF"
    r"\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F"
    r"\U0001FA70-\U0001FAFF"
    r"\u2600-\u26FF"
    r"\u2700-\u27BF"
    r"]",
    flags=re.UNICODE
)

FORBIDDEN_DASHES = ["\u2014", "\u2013"]  # em-dash and en-dash


def test_no_forbidden_symbols():
    project_root = Path(__file__).resolve().parent
    extensions = {".py", ".html", ".css", ".js", ".md", ".txt", ".example"}
    violations = []

    for file_path in project_root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part.startswith(".") for part in file_path.parts if part != ".env.example"):
            continue
        if file_path.name == "reminders.db":
            continue
        if file_path.suffix not in extensions and not file_path.name.startswith(".env"):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            for dash in FORBIDDEN_DASHES:
                if dash in line:
                    violations.append(f"[LONG DASH] {file_path.name}:{line_no} -> {line.strip()}")
            emojis = EMOJI_PATTERN.findall(line)
            if emojis:
                violations.append(f"[EMOJI] {file_path.name}:{line_no} -> {emojis} in: {line.strip()}")

    if violations:
        print("ОШИБКА: Обнаружены запрещенные символы (длинные тире или эмодзи):")
        for v in violations:
            print("  ", v)
        sys.exit(1)
    else:
        print("ПРОВЕРКА 1: Запрещенные символы (тире и эмодзи) отсутствуют во всех файлах проекта.")


async def test_database_and_api():
    print("ПРОВЕРКА 2: Тестирование базы данных...")
    await init_db()

    test_user_id = 999001
    await add_or_update_user(test_user_id, "testuser", "TestName")

    # Создание события
    ev1 = await create_event(
        user_id=test_user_id,
        title="Тестовый дедлайн",
        target_date="2026-12-31",
        target_time="18:00",
        has_time=True
    )
    assert ev1["title"] == "Тестовый дедлайн"
    assert ev1["has_time"] == 1
    assert "2026-12-31T18:00:00" in ev1["target_datetime"]

    # Получение событий
    user_events = await get_user_events(test_user_id, active_only=True)
    assert len(user_events) >= 1

    # Обновление
    ev_updated = await update_event(
        event_id=ev1["id"],
        user_id=test_user_id,
        title="Обновленный дедлайн",
        target_date="2026-12-31",
        target_time="20:00",
        has_time=True
    )
    assert ev_updated["title"] == "Обновленный дедлайн"

    # Дайджест
    digest_events = await get_all_active_events_for_digest()
    assert any(e["id"] == ev1["id"] for e in digest_events)

    # Проверка наступивших событий
    due_events = await get_due_events("2099-01-01T00:00:00")
    assert any(e["id"] == ev1["id"] for e in due_events)

    # Отметка о завершении
    await mark_event_completed(ev1["id"])
    active_after = await get_user_events(test_user_id, active_only=True)
    assert not any(e["id"] == ev1["id"] for e in active_after)

    # Удаление
    ev2 = await create_event(
        user_id=test_user_id,
        title="Событие под удаление",
        target_date="2026-11-30"
    )
    deleted = await delete_event(ev2["id"], test_user_id)
    assert deleted is True

    print("База данных работает корректно.")

    print("ПРОВЕРКА 3: Тестирование HTTP API и статических файлов...")
    app = setup_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Health check
        resp = await client.get("/api/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

        # POST /api/events
        post_resp = await client.post(
            "/api/events",
            json={
                "user_id": test_user_id,
                "title": "API Тест",
                "target_date": "2026-12-25",
                "target_time": "14:00",
                "has_time": True
            }
        )
        assert post_resp.status == 201
        created_json = await post_resp.json()
        new_id = created_json["event"]["id"]

        # GET /api/events
        get_resp = await client.get(f"/api/events?user_id={test_user_id}")
        assert get_resp.status == 200
        get_json = await get_resp.json()
        assert any(e["id"] == new_id for e in get_json["events"])

        # PUT /api/events/{id}
        put_resp = await client.put(
            f"/api/events/{new_id}",
            json={
                "user_id": test_user_id,
                "title": "API Тест Обновлен",
                "target_date": "2026-12-25",
                "target_time": "15:00",
                "has_time": True
            }
        )
        assert put_resp.status == 200

        # DELETE /api/events/{id}
        del_resp = await client.delete(f"/api/events/{new_id}?user_id={test_user_id}")
        assert del_resp.status == 200

        # Static Mini App index.html
        idx_resp = await client.get("/")
        assert idx_resp.status == 200
        html_text = await idx_resp.text()
        assert "Напоминания" in html_text
        assert "telegram-web-app.js" in html_text

        print("HTTP API и статика работают корректно.")
    finally:
        await client.close()


if __name__ == "__main__":
    test_no_forbidden_symbols()
    asyncio.run(test_database_and_api())
    print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
