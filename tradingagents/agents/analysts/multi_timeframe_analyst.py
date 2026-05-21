"""Multi-Timeframe Analyst Agent.

Runs four independent technical analyses over:
  - 1 Day   (short-term, last 30 trading days)
  - 1 Week  (medium-term, last 90 trading days)
  - 1 Month (macro-trend, last 252 trading days / ~1 year)
  - 1 Year  (secular background, last 504 trading days / ~2 years)

Each sub-analyst calls get_stock_data + get_indicators for its window and
emits a directional bias score: Bullish / Neutral / Bearish plus confidence
reasoning. The output is stored as ``multi_timeframe_report`` in AgentState
and later consumed by the Consensus Agent.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict

import yfinance as yf

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

# Mapping: label → calendar-day lookback
_TIMEFRAMES: Dict[str, int] = {
    "1D":  30,    # last ~30 calendar days  → ~21 trading days
    "1W":  90,    # last ~90 calendar days  → ~63 trading days
    "1M": 365,    # last 1 year             → ~252 trading days
    "1Y": 730,    # last 2 years            → ~504 trading days (secular)
}

# Indicators chosen per timeframe for complementary coverage
_INDICATORS: Dict[str, str] = {
    "1D":  "close_10_ema, rsi, macdh, atr",
    "1W":  "close_50_sma, macd, macds, boll, boll_ub, boll_lb, rsi, vwma",
    "1M":  "close_200_sma, close_50_sma, macd, rsi, atr, boll",
    "1Y":  "close_200_sma, rsi, atr, vwma",
}


def _date_range(trade_date: str, lookback_days: int):
    """Return (start_date_str, end_date_str) for a given lookback window."""
    end = date.fromisoformat(trade_date)
    start = end - timedelta(days=lookback_days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _fetch_ohlcv(ticker: str, start: str, end: str) -> str:
    """Fetch OHLCV via yfinance and return a compact CSV-like string."""
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return f"No data available for {ticker} from {start} to {end}."
        # Keep only essential columns, round to 2 dp
        df = df[["Open", "High", "Low", "Close", "Volume"]].round(2)
        return df.tail(30).to_string()
    except Exception as exc:
        return f"Error fetching data for {ticker}: {exc}"


def _compute_indicators(ticker: str, trade_date: str, lookback_days: int) -> str:
    """Compute a set of standard indicators using stockstats via the route_to_vendor path."""
    from tradingagents.dataflows.interface import route_to_vendor
    results = []
    tf_key = next(
        (k for k, v in _TIMEFRAMES.items() if v == lookback_days),
        "custom"
    )
    for ind in _INDICATORS.get(tf_key, "rsi, macd, close_50_sma").split(", "):
        ind = ind.strip().lower()
        try:
            out = route_to_vendor(
                "get_indicators", ticker, ind, trade_date, lookback_days
            )
            results.append(f"[{ind.upper()}]\n{out}")
        except Exception as exc:
            results.append(f"[{ind.upper()}] Error: {exc}")
    return "\n\n".join(results)


# ─────────────────────────────────────────────────────────────────────────────
# Analyst factory
# ─────────────────────────────────────────────────────────────────────────────

def create_multi_timeframe_analyst(llm: Any):
    """Return a LangGraph node that performs multi-timeframe technical analysis.

    The node does NOT use tool-calling; it fetches all data directly (avoiding
    extra round-trips and graph edges) and calls the LLM once with a rich,
    pre-assembled context to produce a structured multi-timeframe report.
    """

    def multi_timeframe_analyst_node(state: Dict[str, Any]) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage

        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # ── 1. Gather data for all four timeframes ──────────────────────────
        sections = []
        for tf_label, lookback in _TIMEFRAMES.items():
            start, end = _date_range(trade_date, lookback)
            ohlcv = _fetch_ohlcv(ticker, start, end)
            indicators = _compute_indicators(ticker, trade_date, lookback)
            sections.append(
                f"## Timeframe: {tf_label}  |  Window: {start} → {end}\n\n"
                f"### OHLCV (last 30 rows)\n```\n{ohlcv}\n```\n\n"
                f"### Technical Indicators\n{indicators}"
            )

        data_block = "\n\n---\n\n".join(sections)

        # ── 2. Build the prompt ─────────────────────────────────────────────
        system_prompt = f"""You are an elite quantitative analyst specializing in multi-timeframe technical analysis.
{instrument_context}

Your task is to analyze {ticker} across FOUR timeframes and produce a structured report.

For each timeframe you will receive OHLCV price data and pre-computed technical indicators.
Timeframes and their investment horizons:
  • 1D  (Daily, ~30 trading days)   — Short-term momentum & entry timing
  • 1W  (Weekly, ~90 trading days)  — Medium-term trend direction
  • 1M  (Monthly, ~252 trading days) — Macro trend & regime identification
  • 1Y  (Yearly, ~504 trading days)  — Secular background / market structure

For EACH timeframe, output:
  1. **Trend Direction**: Bullish / Neutral / Bearish
  2. **Confidence**: High / Medium / Low
  3. **Key Evidence**: 2-4 bullet points citing specific indicator values
  4. **Actionable Insight**: one sentence a trader can act on

After analyzing all four timeframes, produce a **Multi-Timeframe Summary Bulleted List**
with details for each timeframe: Timeframe, Trend, Confidence, and Key Signal.

Finally, write a **Composite Directional Bias** paragraph (3-5 sentences) that synthesizes
all four timeframes into a single forward-looking view, noting any timeframe conflicts.

Be precise — quote exact indicator values. Be actionable.
CRITICAL INSTRUCTION: DO NOT copy, paste, or output the raw OHLCV CSV data or large blocks of numbers in your report. Provide ONLY your analysis, insights, and the final summary. DO NOT output any markdown tables under any circumstances; instead, present all structured summaries and metrics as neat, readable bulleted lists.

CRITICAL — you MUST end your entire response with the following VOTE_BLOCK.
Replace each VALUE with exactly one word: Bullish, Neutral, or Bearish.
Do NOT add any text after the closing marker.

VOTE_BLOCK
1D=VALUE
1W=VALUE
1M=VALUE
1Y=VALUE
END_VOTE_BLOCK
{lang_instruction}
"""

        user_message = (
            f"Here is the market data for {ticker} as of {trade_date}:\n\n"
            f"{data_block}\n\n"
            "Please produce the full multi-timeframe analysis report as described."
        )

        from langchain_core.prompts import ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", "{user_message}")]
        )
        chain = prompt | llm

        result = chain.invoke({"user_message": user_message})

        report_text = (
            result.content
            if hasattr(result, "content")
            else str(result)
        )

        report = (
            f"# Multi-Timeframe Technical Analysis — {ticker} ({trade_date})\n\n"
            f"{report_text}"
        )

        return {
            "messages": [HumanMessage(content=report, name="Multi-Timeframe Analyst")],
            "multi_timeframe_report": report,
        }

    return multi_timeframe_analyst_node
