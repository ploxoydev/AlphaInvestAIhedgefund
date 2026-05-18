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

# LLM provider
LLM_PROVIDER = "google"

# ── API Key rotation ──────────────────────────────────────────────────────────
# Each key should be from a DIFFERENT Google Cloud project (separate quotas).
# Add more keys as GOOGLE_API_KEY_2, GOOGLE_API_KEY_3, etc. in .env / Render env vars.
import os as _os
GOOGLE_API_KEYS: list[str] = [k for k in [
    _os.getenv("GOOGLE_API_KEY", ""),
    _os.getenv("GOOGLE_API_KEY_2", ""),
    _os.getenv("GOOGLE_API_KEY_3", ""),
] if k]

# ── Model rotation ────────────────────────────────────────────────────────────
# Each model has its own separate daily/minute quota.
# On 429 exhaustion we rotate to the next model automatically.
FALLBACK_MODELS: list[str] = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.0-flash-lite",
]

# Primary model defaults (first in rotation list)
QUICK_THINK_LLM = FALLBACK_MODELS[0]
DEEP_THINK_LLM  = FALLBACK_MODELS[0]

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
