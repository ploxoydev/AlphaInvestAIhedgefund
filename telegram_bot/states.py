"""FSM states for the Telegram bot conversation flow."""

from aiogram.fsm.state import State, StatesGroup


class AnalysisFlow(StatesGroup):
    waiting_ticker   = State()   # Step 1: user enters ticker
    waiting_language = State()   # Step 2: user picks language
    confirming       = State()   # Step 3: confirm → launch
    running          = State()   # Analysis in progress
