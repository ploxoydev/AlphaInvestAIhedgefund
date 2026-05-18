"""
Hardcoded configuration for the Telegram bot.
All settings are fixed — users only choose ticker and language.
"""

import os

# ── Bot ───────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── TradingAgents — hardcoded settings ───────────────────────────────────────
ANALYSTS = ["market", "social", "news", "fundamentals"]

# Research depth: medium = max_debate_rounds=1, max_risk_discuss_rounds=1
MAX_DEBATE_ROUNDS = 1
MAX_RISK_DISCUSS_ROUNDS = 1

# LLM provider and models
LLM_PROVIDER = "google"
QUICK_THINK_LLM = "gemini-3.1-flash"
DEEP_THINK_LLM  = "gemini-3.0-flash"

# Thinking mode — always enabled (high)
GOOGLE_THINKING_LEVEL = "high"

# Rate limit: 1 analysis per user per 3 hours
RATE_LIMIT_SECONDS = 10800

# Max concurrent analyses running at the same time
MAX_CONCURRENT = 5

# ── Language options (shown to user) ─────────────────────────────────────────
LANGUAGES = {
    "🇷🇺 Русский":    "Russian",
    "🇬🇧 English":    "English",
    "🇨🇳 中文":        "Chinese",
    "🇯🇵 日本語":      "Japanese",
    "🇰🇷 한국어":     "Korean",
    "🇮🇳 हिन्दी":     "Hindi",
    "🇪🇸 Español":    "Spanish",
    "🇩🇪 Deutsch":    "German",
    "🇫🇷 Français":   "French",
    "🇸🇦 عربي":       "Arabic",
}
