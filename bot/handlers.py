from datetime import datetime, timedelta
import re
from typing import Optional
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    get_after_create_keyboard,
    get_cancel_keyboard,
    get_date_presets_keyboard,
    get_event_actions_keyboard,
    get_start_keyboard,
    get_time_choice_keyboard,
    get_time_presets_keyboard,
)
from bot.states import EventCreation
from config import WEBAPP_URL
from database import (
    add_or_update_user,
    create_event,
    delete_event,
    get_user_events,
)

router = Router(name="main_router")


def format_remaining_time(target_dt_iso: str, has_time: bool) -> str:
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


def parse_date_input(text: str) -> Optional[str]:
    text = text.strip()
    patterns = [
        ("%d.%m.%Y", r"^\d{1,2}\.\d{1,2}\.\d{4}$"),
        ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
        ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
    ]
    for date_fmt, regex in patterns:
        if re.match(regex, text):
            try:
                dt = datetime.strptime(text, date_fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def parse_time_input(text: str) -> Optional[str]:
    text = text.strip()
    if re.match(r"^\d{1,2}:\d{2}$", text):
        try:
            dt = datetime.strptime(text, "%H:%M")
            return dt.strftime("%H:%M")
        except ValueError:
            return None
    return None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    if user:
        await add_or_update_user(user.id, user.username, user.first_name)

    text = (
        "Трекер важных событий и обратного отсчета времени.\n\n"
        "Следите за приближением ключевых дат в мини-приложении или управляйте напоминаниями прямо в чате."
    )
    await message.answer(text, reply_markup=get_start_keyboard(WEBAPP_URL))


@router.callback_query(F.data == "cancel_action")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Действие отменено")
    if callback.message:
        await callback.message.edit_text(
            "Создание напоминания отменено.",
            reply_markup=get_start_keyboard(WEBAPP_URL)
        )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Создание напоминания отменено.", reply_markup=get_start_keyboard(WEBAPP_URL))


@router.callback_query(F.data == "btn_my_events")
async def callback_my_events(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    events = await get_user_events(user_id=user_id, active_only=True)

    if not events:
        text = "У вас пока нет активных напоминаний."
        if callback.message:
            await callback.message.answer(text, reply_markup=get_start_keyboard(WEBAPP_URL))
        return

    if callback.message:
        await callback.message.answer("Активные напоминания:")

    for event in events:
        title = event["title"]
        target_date = event["target_date"]
        target_time = event["target_time"]
        has_time = bool(event["has_time"])
        remaining = format_remaining_time(event["target_datetime"], has_time)

        time_part = f" {target_time}" if has_time and target_time else ""
        msg_text = (
            f"Событие: {title}\n"
            f"Дата цели: {target_date}{time_part}\n"
            f"Осталось: {remaining}"
        )
        if callback.message:
            await callback.message.answer(
                msg_text,
                reply_markup=get_event_actions_keyboard(event["id"])
            )


@router.message(Command("events"))
@router.message(Command("list"))
async def cmd_events(message: Message):
    user_id = message.from_user.id
    events = await get_user_events(user_id=user_id, active_only=True)

    if not events:
        await message.answer("У вас пока нет активных напоминаний.", reply_markup=get_start_keyboard(WEBAPP_URL))
        return

    await message.answer("Активные напоминания:")
    for event in events:
        title = event["title"]
        target_date = event["target_date"]
        target_time = event["target_time"]
        has_time = bool(event["has_time"])
        remaining = format_remaining_time(event["target_datetime"], has_time)

        time_part = f" {target_time}" if has_time and target_time else ""
        msg_text = (
            f"Событие: {title}\n"
            f"Дата цели: {target_date}{time_part}\n"
            f"Осталось: {remaining}"
        )
        await message.answer(msg_text, reply_markup=get_event_actions_keyboard(event["id"]))


@router.callback_query(F.data.startswith("delete_event:"))
async def callback_delete_event(callback: CallbackQuery):
    event_id_str = callback.data.split(":")[1]
    try:
        event_id = int(event_id_str)
    except ValueError:
        await callback.answer("Некорректный ID")
        return

    user_id = callback.from_user.id
    success = await delete_event(event_id, user_id)
    if success:
        await callback.answer("Событие удалено")
        if callback.message:
            await callback.message.edit_text("Событие успешно удалено из списка.")
    else:
        await callback.answer("Событие не найдено")


@router.callback_query(F.data == "btn_add_event")
async def callback_add_event(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(EventCreation.title)
    text = "Введите название события:"
    if callback.message:
        await callback.message.answer(text, reply_markup=get_cancel_keyboard())


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    await state.set_state(EventCreation.title)
    await message.answer("Введите название события:", reply_markup=get_cancel_keyboard())


@router.message(EventCreation.title)
async def process_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Введите текст:")
        return

    await state.update_data(title=title)
    await state.set_state(EventCreation.date)

    text = (
        f"Событие: {title}\n\n"
        "Укажите дату события в формате ДД.ММ.ГГГГ (например, 25.12.2026) или выберите вариант ниже:"
    )
    await message.answer(text, reply_markup=get_date_presets_keyboard())


@router.callback_query(F.data.startswith("date_preset:"), EventCreation.date)
async def process_date_preset(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    offset_days = int(callback.data.split(":")[1])
    target_dt = datetime.now() + timedelta(days=offset_days)
    target_date = target_dt.strftime("%Y-%m-%d")

    await state.update_data(target_date=target_date)
    await state.set_state(EventCreation.time_choice)

    if callback.message:
        await callback.message.edit_text(
            f"Выбрана дата: {target_date}\n\nУказать точное время события?",
            reply_markup=get_time_choice_keyboard()
        )


@router.message(EventCreation.date)
async def process_date_text(message: Message, state: FSMContext):
    parsed = parse_date_input(message.text or "")
    if not parsed:
        await message.answer(
            "Не удалось распознать дату. Введите дату в формате ДД.ММ.ГГГГ (например, 25.12.2026):",
            reply_markup=get_date_presets_keyboard()
        )
        return

    await state.update_data(target_date=parsed)
    await state.set_state(EventCreation.time_choice)
    await message.answer(
        f"Выбрана дата: {parsed}\n\nУказать точное время события?",
        reply_markup=get_time_choice_keyboard()
    )


@router.callback_query(F.data == "time_choice:none", EventCreation.time_choice)
async def process_time_none(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    title = data.get("title", "")
    target_date = data.get("target_date", "")
    user_id = callback.from_user.id

    event = await create_event(
        user_id=user_id,
        title=title,
        target_date=target_date,
        target_time="",
        has_time=False
    )
    await state.clear()

    remaining = format_remaining_time(event["target_datetime"], False)
    msg_text = (
        "Событие сохранено.\n\n"
        f"Название: {title}\n"
        f"Дата цели: {target_date}\n"
        f"Осталось: {remaining}"
    )
    if callback.message:
        await callback.message.edit_text(msg_text, reply_markup=get_after_create_keyboard(WEBAPP_URL))


@router.callback_query(F.data == "time_choice:exact", EventCreation.time_choice)
async def process_time_exact_choice(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(EventCreation.exact_time)
    text = "Укажите время в формате ЧЧ:ММ (например, 14:30) или выберите вариант ниже:"
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_time_presets_keyboard())


@router.callback_query(F.data.startswith("time_preset:"), EventCreation.exact_time)
async def process_time_preset(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    target_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    title = data.get("title", "")
    target_date = data.get("target_date", "")
    user_id = callback.from_user.id

    event = await create_event(
        user_id=user_id,
        title=title,
        target_date=target_date,
        target_time=target_time,
        has_time=True
    )
    await state.clear()

    remaining = format_remaining_time(event["target_datetime"], True)
    msg_text = (
        "Событие сохранено.\n\n"
        f"Название: {title}\n"
        f"Дата и время цели: {target_date} {target_time}\n"
        f"Осталось: {remaining}"
    )
    if callback.message:
        await callback.message.edit_text(msg_text, reply_markup=get_after_create_keyboard(WEBAPP_URL))


@router.message(EventCreation.exact_time)
async def process_time_text(message: Message, state: FSMContext):
    parsed_time = parse_time_input(message.text or "")
    if not parsed_time:
        await message.answer(
            "Некорректный формат времени. Введите время в формате ЧЧ:ММ (например, 09:30):",
            reply_markup=get_time_presets_keyboard()
        )
        return

    data = await state.get_data()
    title = data.get("title", "")
    target_date = data.get("target_date", "")
    user_id = message.from_user.id

    event = await create_event(
        user_id=user_id,
        title=title,
        target_date=target_date,
        target_time=parsed_time,
        has_time=True
    )
    await state.clear()

    remaining = format_remaining_time(event["target_datetime"], True)
    msg_text = (
        "Событие сохранено.\n\n"
        f"Название: {title}\n"
        f"Дата и время цели: {target_date} {parsed_time}\n"
        f"Осталось: {remaining}"
    )
    await message.answer(msg_text, reply_markup=get_after_create_keyboard(WEBAPP_URL))
