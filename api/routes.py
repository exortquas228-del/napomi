import json
from pathlib import Path
from aiohttp import web
from config import STATIC_DIR
from database import (
    create_event,
    delete_event,
    get_event_by_id,
    get_user_events,
    update_event,
)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        except Exception as ex:
            response = web.json_response(
                {"error": "Внутренняя ошибка сервера: " + str(ex)},
                status=500
            )

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def get_events_handler(request: web.Request) -> web.Response:
    user_id_param = request.query.get("user_id")
    if not user_id_param:
        return web.json_response({"error": "Параметр user_id обязателен"}, status=400)

    try:
        user_id = int(user_id_param)
    except ValueError:
        return web.json_response({"error": "Некорректный user_id"}, status=400)

    events = await get_user_events(user_id=user_id, active_only=True)
    return web.json_response({"events": events})


async def create_event_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Некорректный JSON"}, status=400)

    user_id = data.get("user_id")
    title = data.get("title", "").strip()
    target_date = data.get("target_date", "").strip()
    target_time = data.get("target_time", "")
    has_time = bool(data.get("has_time", False))

    if not user_id:
        return web.json_response({"error": "user_id обязателен"}, status=400)
    if not title:
        return web.json_response({"error": "Название события не может быть пустым"}, status=400)
    if not target_date:
        return web.json_response({"error": "Дата события обязательна"}, status=400)

    try:
        user_id_int = int(user_id)
    except ValueError:
        return web.json_response({"error": "Некорректный user_id"}, status=400)

    event = await create_event(
        user_id=user_id_int,
        title=title,
        target_date=target_date,
        target_time=target_time,
        has_time=has_time
    )
    return web.json_response({"success": True, "event": event}, status=201)


async def update_event_handler(request: web.Request) -> web.Response:
    event_id_str = request.match_info.get("id")
    try:
        event_id = int(event_id_str)
    except (ValueError, TypeError):
        return web.json_response({"error": "Некорректный ID события"}, status=400)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Некорректный JSON"}, status=400)

    user_id = data.get("user_id")
    title = data.get("title", "").strip()
    target_date = data.get("target_date", "").strip()
    target_time = data.get("target_time", "")
    has_time = bool(data.get("has_time", False))

    if not user_id or not title or not target_date:
        return web.json_response({"error": "Поля user_id, title и target_date обязательны"}, status=400)

    try:
        user_id_int = int(user_id)
    except ValueError:
        return web.json_response({"error": "Некорректный user_id"}, status=400)

    updated = await update_event(
        event_id=event_id,
        user_id=user_id_int,
        title=title,
        target_date=target_date,
        target_time=target_time,
        has_time=has_time
    )

    if not updated:
        return web.json_response({"error": "Событие не найдено или нет прав для изменения"}, status=404)

    return web.json_response({"success": True, "event": updated})


async def delete_event_handler(request: web.Request) -> web.Response:
    event_id_str = request.match_info.get("id")
    user_id_param = request.query.get("user_id")

    if not user_id_param:
        return web.json_response({"error": "Параметр user_id обязателен"}, status=400)

    try:
        event_id = int(event_id_str)
        user_id = int(user_id_param)
    except (ValueError, TypeError):
        return web.json_response({"error": "Некорректные параметры ID или user_id"}, status=400)

    deleted = await delete_event(event_id=event_id, user_id=user_id)
    if not deleted:
        return web.json_response({"error": "Событие не найдено"}, status=404)

    return web.json_response({"success": True})


async def index_handler(request: web.Request) -> web.Response:
    index_path = Path(STATIC_DIR) / "index.html"
    if not index_path.exists():
        return web.Response(text="Mini App frontend is not installed.", status=404)
    return web.FileResponse(index_path)


def setup_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])

    # REST API
    app.router.add_get("/api/health", health_handler)
    app.router.add_get("/api/events", get_events_handler)
    app.router.add_post("/api/events", create_event_handler)
    app.router.add_put("/api/events/{id}", update_event_handler)
    app.router.add_delete("/api/events/{id}", delete_event_handler)

    # Static assets and WebApp entrypoint
    app.router.add_get("/", index_handler)
    app.router.add_get("/app", index_handler)

    static_path = Path(STATIC_DIR)
    if static_path.exists():
        app.router.add_static("/static", str(static_path), follow_symlinks=True)

    return app
