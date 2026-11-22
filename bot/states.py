from aiogram.fsm.state import State, StatesGroup


class EventCreation(StatesGroup):
    title = State()
    date = State()
    time_choice = State()
    exact_time = State()
