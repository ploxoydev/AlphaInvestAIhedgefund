"""Consensus Agent.

Reads the multi-timeframe report produced by the Multi-Timeframe Analyst and
applies a weighted voting rule to produce a single **consensus signal**:

  Weights
  -------
  1Y  (secular)   → 1 vote  (background context)
  1M  (macro)     → 2 votes (primary trend)
  1W  (medium)    → 2 votes (trading trend)
  1D  (short)     → 1 vote  (entry timing)

  Mapping: Bullish → +1, Neutral → 0, Bearish → −1
  Weighted score range: [−6, +6]

  Decision rules:
  ---------------
  score ≥ +3  → STRONG BUY  (all major TFs aligned bullish)
  score ≥ +1  → BUY         (majority bullish)
  score = 0   → HOLD        (conflicting or all neutral)
  score ≤ −1  → SELL        (majority bearish)
  score ≤ −3  → STRONG SELL (all major TFs aligned bearish)

The agent also detects **timeframe conflicts** (e.g., 1D bearish but 1M
bullish) and flags them with a risk warning so downstream agents can apply
appropriate position-sizing caution.

Output is stored in ``consensus_report`` in AgentState.
"""

from __future__ import annotations

import re
from typing import Any, Dict


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_TF_WEIGHTS: Dict[str, int] = {
    "1Y": 1,
    "1M": 2,
    "1W": 2,
    "1D": 1,
}

_BIAS_SCORE: Dict[str, int] = {
    "bullish": +1,
    "neutral":  0,
    "bearish": -1,
}


def _normalize_direction(word: str) -> str:
    """Normalise any language's direction word to Bullish / Neutral / Bearish."""
    w = word.strip().lower()
    bullish_words = {
        # EN
        "bullish",
        # RU
        "бычий", "бычья", "бычье", "бычьи", "восходящий", "восходящая",
        "растущий", "растущая", "позитивный", "позитивная",
        # DE
        "bullis", "aufwarts",
        # FR
        "haussier", "haussiere",
        # ES
        "alcista",
        # ZH
        "看涨", "多头",
        # JA
        "強気",
    }
    bearish_words = {
        # EN
        "bearish",
        # RU
        "медвежий", "медвежья", "медвежье", "медвежьи", "нисходящий",
        "нисходящая", "падающий", "падающая", "негативный", "негативная",
        # DE
        "baaris", "abwarts",
        # FR
        "baissier", "baissiere",
        # ES
        "bajista",
        # ZH
        "看跌", "空头",
        # JA
        "弱気",
    }
    neutral_words = {
        # EN
        "neutral",
        # RU
        "нейтральный", "нейтральная", "нейтральное", "нейтральные",
        "боковой", "боковая", "смешанный", "смешанная",
        # DE
        "neutral", "seitwarts",
        # FR
        "neutre",
        # ES
        "neutral",
        # ZH
        "中性",
        # JA
        "中立",
    }
    if w in bullish_words:
        return "Bullish"
    if w in bearish_words:
        return "Bearish"
    if w in neutral_words:
        return "Neutral"
    return ""  # unrecognised


# Regex that matches direction words in all supported languages (used in strategies 1-3)
_DIRECTIONS_RX = re.compile(
    r"\b("
    # English
    r"Bullish|Neutral|Bearish"
    # Russian
    r"|Бычий|Бычья|Бычье|Бычьи|Медвежий|Медвежья|Медвежье|Медвежьи"
    r"|Нейтральный|Нейтральная|Нейтральное|Нейтральные"
    r"|Восходящий|Восходящая|Нисходящий|Нисходящая"
    r"|Растущий|Растущая|Падающий|Падающая"
    r"|Боковой|Боковая|Позитивный|Позитивная|Негативный|Негативная"
    # German / French / Spanish (common terms)
    r"|Haussier|Baissier|Alcista|Bajista"
    r")\b",
    re.IGNORECASE | re.UNICODE,
)


def _extract_trends(multi_tf_report: str) -> Dict[str, str]:
    """Parse trend directions using 4 strategies in order of reliability.

    Strategy 0 - VOTE_BLOCK (highest priority):
        Parses the structured block the multi-timeframe analyst always emits:
            VOTE_BLOCK\n1D=Bullish\n...\nEND_VOTE_BLOCK
        English words guaranteed by the prompt.
    Strategy 1 - Flexible table scan:
        Tolerates bold/italic markdown inside table cells, multilingual.
    Strategy 2 - Section-header proximity (1200 chars), multilingual.
    Strategy 3 - Brute-force proximity (800 chars), multilingual.
    """
    import logging
    log = logging.getLogger(__name__)

    found: Dict[str, str] = {}

    # -- Strategy 0: Parse VOTE_BLOCK (fastest, 100% reliable when present) --
    vb = re.search(
        r"VOTE_BLOCK\s*(.*?)\s*END_VOTE_BLOCK",
        multi_tf_report,
        re.IGNORECASE | re.DOTALL,
    )
    if vb:
        for line in vb.group(1).splitlines():
            # Accept both English (Bullish) and Russian (Бычий) values
            kv = re.match(
                r"(1D|1W|1M|1Y)\s*=\s*(\S+)",
                line.strip(),
                re.IGNORECASE | re.UNICODE,
            )
            if kv:
                normalised = _normalize_direction(kv.group(2))
                if normalised:
                    found[kv.group(1).upper()] = normalised
        if len(found) == 4:
            log.info("[Consensus] VOTE_BLOCK parsed: %s", found)
            return found
        log.warning("[Consensus] Partial VOTE_BLOCK (%d/4 TFs). Running fallbacks.", len(found))

    md = r"\**\s*"  # optional bold/italic markdown wrappers

    # ── Strategy 1: Markdown table (multilingual, tolerates ** wrapping) ──────
    tbl = re.compile(
        rf"\|\s*{md}(1D|1W|1M|1Y){md}\s*\|\s*{md}({_DIRECTIONS_RX.pattern}){md}\s*\|",
        re.IGNORECASE | re.UNICODE,
    )
    for m in tbl.finditer(multi_tf_report):
        tf = m.group(1).upper()
        normalised = _normalize_direction(m.group(2))
        if normalised:
            found[tf] = normalised

    # ── Strategy 2: Section-header + direction keyword within 1200 chars ──────
    if len(found) < 4:
        hdr_re = re.compile(
            r"(?:#{1,4}\s*(?:Timeframe[:\s|]+)?|\*\*+\s*)?(1D|1W|1M|1Y)\b",
            re.IGNORECASE,
        )
        for hdr in hdr_re.finditer(multi_tf_report):
            tf = hdr.group(1).upper()
            if tf in found:
                continue
            window = multi_tf_report[hdr.start(): hdr.start() + 1200]
            m = _DIRECTIONS_RX.search(window)
            if m:
                normalised = _normalize_direction(m.group(1))
                if normalised:
                    found[tf] = normalised

    # ── Strategy 3: Brute-force proximity (800 chars after any TF mention) ────
    if len(found) < 4:
        for tf in ["1D", "1W", "1M", "1Y"]:
            if tf in found:
                continue
            for hit in re.finditer(rf"\b{re.escape(tf)}\b", multi_tf_report, re.IGNORECASE):
                window = multi_tf_report[hit.start(): hit.start() + 800]
                m = _DIRECTIONS_RX.search(window)
                if m:
                    normalised = _normalize_direction(m.group(1))
                    if normalised:
                        found[tf] = normalised
                        break

    log.info(
        "[Consensus] Extracted trends: %s  (missing TFs default to Neutral)",
        found,
    )
    return found



def _compute_score(trends: Dict[str, str]) -> int:
    score = 0
    for tf, weight in _TF_WEIGHTS.items():
        bias = trends.get(tf, "Neutral").lower()
        score += _BIAS_SCORE.get(bias, 0) * weight
    return score


def _score_to_action(score: int) -> str:
    if score >= 3:
        return "STRONG BUY"
    if score >= 1:
        return "BUY"
    if score <= -3:
        return "STRONG SELL"
    if score <= -1:
        return "SELL"
    return "HOLD"


def _detect_conflicts(trends: Dict[str, str]) -> str:
    """Identify timeframe disagreements (short vs. long term)."""
    conflicts = []
    pairs = [("1D", "1W"), ("1D", "1M"), ("1D", "1Y"), ("1W", "1M"), ("1W", "1Y")]
    for a, b in pairs:
        ta = trends.get(a, "Neutral").lower()
        tb = trends.get(b, "Neutral").lower()
        if ta != "neutral" and tb != "neutral" and ta != tb:
            conflicts.append(f"{a} ({trends[a]}) ≠ {b} ({trends[b]})")
    if not conflicts:
        return "None — all timeframes are aligned."
    return "; ".join(conflicts)


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory
# ─────────────────────────────────────────────────────────────────────────────

def create_consensus_agent(llm: Any):
    """Return a LangGraph node that synthesizes the multi-timeframe report
    into a weighted consensus signal and produces a qualitative narrative.
    """

    def consensus_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
        from langchain_core.messages import HumanMessage
        from langchain_core.prompts import ChatPromptTemplate
        from tradingagents.agents.utils.agent_utils import (
            build_instrument_context,
            get_language_instruction,
        )

        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        multi_tf_report = state.get("multi_timeframe_report", "")
        instrument_context = build_instrument_context(ticker)
        lang_instruction = get_language_instruction()

        # ── Quantitative scoring (deterministic, no LLM needed) ───────────
        trends = _extract_trends(multi_tf_report)
        score = _compute_score(trends)
        action = _score_to_action(score)
        conflicts = _detect_conflicts(trends)

        # Build trend table string for the prompt
        trend_lines = "\n".join(
            f"  {tf}: {trends.get(tf, 'Unknown')} (weight={_TF_WEIGHTS[tf]}, "
            f"vote={_BIAS_SCORE.get(trends.get(tf,'Neutral').lower(), 0) * _TF_WEIGHTS[tf]:+d})"
            for tf in ["1Y", "1M", "1W", "1D"]
        )

        system_prompt = f"""You are the Consensus Agent — the final arbiter of a multi-timeframe technical analysis.
{instrument_context}

You have already received a detailed multi-timeframe report for {ticker} as of {trade_date}.
A deterministic weighted-vote model has already computed the following:

TREND SUMMARY
─────────────
{trend_lines}

Weighted Consensus Score : {score:+d}  (range: −6 to +6)
Quantitative Signal       : {action}
Timeframe Conflicts       : {conflicts}

YOUR TASK
─────────
1. Validate (or gently challenge) the quantitative signal using the qualitative
   evidence in the multi-timeframe report.
2. Write a structured **Consensus Report** with these sections:
   a) **📊 Weighted Vote Summary** — reproduce the score table above as a neat bulleted list (including timeframe, direction, weight, and calculated vote).
   b) **🎯 Consensus Signal** — state the signal ({action}) and explain why the
      weighted score of {score:+d} is or is not fully supported by the qualitative evidence.
   c) **⚠️ Timeframe Conflicts** — describe any conflicts and their implications
      for position sizing or trade timing.
   d) **📋 Trading Recommendation** — a concrete, risk-aware recommendation
      (entry zone, preferred timeframe for entry, risk level: High/Medium/Low,
      suggested position size as % of portfolio: small/medium/full).
   e) **🔮 Key Risk Scenarios** — two bullet points: one bull-case, one bear-case.

Be concise but precise. Quote indicator values from the report where relevant.
CRITICAL INSTRUCTION: DO NOT output any markdown tables under any circumstances; instead, present all structured summaries and tables as neat, readable bulleted lists.
{lang_instruction}
"""

        user_message = (
            f"Here is the full Multi-Timeframe Analysis Report for {ticker}:\n\n"
            f"{multi_tf_report}\n\n"
            "Please produce the Consensus Report as instructed."
        )

        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt), ("human", "{user_message}")]
        )
        chain = prompt | llm
        result = chain.invoke({"user_message": user_message})

        report_text = (
            result.content if hasattr(result, "content") else str(result)
        )

        # ── Assemble final report ─────────────────────────────────────────
        header = (
            f"# Multi-Timeframe Consensus Report\n"
            f"**Ticker**: {ticker} | **Date**: {trade_date} | "
            f"**Signal**: {action} | **Score**: {score:+d}/6\n\n"
        )
        full_report = header + report_text

        return {
            "messages": [HumanMessage(content=full_report, name="Consensus Agent")],
            "consensus_report": full_report,
            "consensus_signal": action,
            "consensus_score": score,
        }

    return consensus_agent_node
