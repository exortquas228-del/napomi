from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def get_start_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=webapp_url))],
        [
            InlineKeyboardButton(text="Добавить напоминание", callback_data="btn_add_event"),
            InlineKeyboardButton(text="Мои напоминания", callback_data="btn_my_events")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel_action")]]
    )


def get_date_presets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="date_preset:0"),
                InlineKeyboardButton(text="Завтра", callback_data="date_preset:1")
            ],
            [
                InlineKeyboardButton(text="Через 7 дней", callback_data="date_preset:7"),
                InlineKeyboardButton(text="Через 30 дней", callback_data="date_preset:30")
            ],
            [
                InlineKeyboardButton(text="Отмена", callback_data="cancel_action")
            ]
        ]
    )


def get_time_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Без точного времени", callback_data="time_choice:none"),
                InlineKeyboardButton(text="Указать время", callback_data="time_choice:exact")
            ],
            [
                InlineKeyboardButton(text="Отмена", callback_data="cancel_action")
            ]
        ]
    )


def get_time_presets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="09:00", callback_data="time_preset:09:00"),
                InlineKeyboardButton(text="12:00", callback_data="time_preset:12:00")
            ],
            [
                InlineKeyboardButton(text="18:00", callback_data="time_preset:18:00"),
                InlineKeyboardButton(text="21:00", callback_data="time_preset:21:00")
            ],
            [
                InlineKeyboardButton(text="Отмена", callback_data="cancel_action")
            ]
        ]
    )


def get_event_actions_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_event:{event_id}")]
        ]
    )


def get_after_create_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text="Мои напоминания", callback_data="btn_my_events"),
                InlineKeyboardButton(text="Добавить еще", callback_data="btn_add_event")
            ]
        ]
    )
