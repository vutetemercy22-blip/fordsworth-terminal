from typing import Dict, List
import streamlit as st
from groq import Groq

from services.market_data_service import format_market_context_for_prompt


DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_groq_client() -> Groq:
    """
    Build Groq client from Streamlit secrets.
    """
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception as exc:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to .streamlit/secrets.toml"
        ) from exc

    return Groq(api_key=api_key)


def format_news_for_prompt(portfolio_news: Dict[str, List[Dict]]) -> str:
    """
    Convert structured news data into text for the LLM prompt.
    Includes article URLs so the final briefing can cite sources.
    """
    sections = []

    for ticker, articles in portfolio_news.items():
        sections.append(f"\n### {ticker}")

        if not articles:
            sections.append("No relevant articles found in the last 24 hours.")
            continue

        for index, article in enumerate(articles, start=1):
            title = article.get("title") or "No title"
            description = article.get("description") or "No description"
            source = article.get("source") or "Unknown source"
            published_at = article.get("published_at") or "Unknown date"
            url = article.get("url") or "No URL provided"

            sections.append(
                f"""
Article {index}
Title: {title}
Source: {source}
Published: {published_at}
Summary: {description}
URL: {url}
""".strip()
            )

    return "\n\n".join(sections)


def format_thesis_context(positions: List[Dict]) -> str:
    """
    Convert portfolio YAML thesis files into prompt context.
    """
    sections = []

    for position in positions:
        thesis = position.get("investment_thesis", {})
        monitoring = position.get("monitoring", {})
        valuation = position.get("valuation", {})

        core_drivers = thesis.get("core_drivers", [])
        metrics = thesis.get("key_metrics_to_monitor", [])
        kill_criteria = thesis.get("kill_criteria", [])

        core_driver_text = "\n".join([f"- {item}" for item in core_drivers]) or "- Not provided"
        metrics_text = "\n".join([f"- {item}" for item in metrics]) or "- Not provided"
        kill_criteria_text = "\n".join([f"- {item}" for item in kill_criteria]) or "- Not provided"

        sections.append(
            f"""
### {position.get("ticker")} — {position.get("company_name")}

Sector: {position.get("sector")}
Portfolio weight: {position.get("portfolio_weight", "N/A")}%
Monitoring priority: {monitoring.get("overnight_news_priority", "normal")}

One-line thesis:
{thesis.get("one_line", "No thesis provided.")}

Core thesis drivers:
{core_driver_text}

Key metrics to monitor:
{metrics_text}

Kill criteria:
{kill_criteria_text}

Valuation reference:
- Bear case: {valuation.get("bear_case", "N/A")}
- Fair value: {valuation.get("fair_value", "N/A")}
- Bull case: {valuation.get("bull_case", "N/A")}
""".strip()
        )

    return "\n\n".join(sections)


def generate_morning_briefing(
    positions: List[Dict],
    portfolio_news: Dict[str, List[Dict]],
    market_context: Dict,
    date_label: str,
) -> str:
    """
    Generate a thesis-aware morning briefing using Groq.
    """
    client = get_groq_client()

    thesis_context = format_thesis_context(positions)
    news_context = format_news_for_prompt(portfolio_news)
    market_context_text = format_market_context_for_prompt(market_context)

    system_prompt = """
You are an institutional-quality buy-side morning analyst.

Your job is to prepare a concise but decision-useful morning briefing for a portfolio manager.

You are not a generic news summariser. You are a thesis-aware analyst.

Rules:
- Filter noise aggressively.
- Do not treat every headline as important.
- Link every important development back to the stored investment thesis.
- Clearly state whether the development strengthens, weakens, is neutral to, or requires monitoring against the thesis.
- Assign urgency: Low, Medium, or High.
- Say whether action is required: Yes or No.
- Do not invent facts outside the supplied thesis, market context, and news context.
- If the supplied news is thin, stale, promotional, or low quality, say so clearly.
- Include source links only from the supplied URLs.
- Use polished institutional investment language.
- Be direct and practical.
""".strip()

    user_prompt = f"""
Prepare the Morning Analyst Briefing for {date_label}.

PORTFOLIO THESIS CONTEXT
{thesis_context}

MARKET CONTEXT
{market_context_text}

NEWS FROM THE LAST 24 HOURS
{news_context}

Use this exact structure:

# Morning Analyst Briefing — {date_label}

## 1. Executive Summary
Give 3–5 bullet points only.
Focus only on what matters to the portfolio.
Mention if there are no major thesis-changing developments.

## 2. Market Context
Summarise the broad market backdrop.
Explain whether rates, FX, indices, or commodities matter for this portfolio today.
If market context is placeholder or incomplete, say that live market data is not yet connected.

## 3. Portfolio-Relevant Developments
For each ticker with genuinely relevant news, use this format:

### TICKER — Company Name

**What happened:**  
Briefly explain the development.

**Why it matters:**  
Explain why the development matters for the investment thesis.

**Thesis impact:** Strengthens / Weakens / Neutral / Monitor

**Urgency:** Low / Medium / High

**Action required:** Yes / No

**Source:** Include the article title and URL.

If a ticker has no meaningful news, do not force a full section for it.

## 4. Position-by-Position Thesis Impact Table
Create a markdown table with these columns:

| Ticker | Overnight Status | Thesis Impact | Urgency | Action Required | Follow-Up |
|---|---|---|---|---|---|

Include every portfolio position.

## 5. Risk Flags
List only risks that need attention.
If there are none, say: "No urgent thesis-level risk flags identified from the supplied information."

## 6. Source Links
Create a clean bullet list of all source links used.
Format:
- TICKER — Article title — URL

Only include URLs supplied in the news context.

## 7. Today’s Analyst To-Do List
List 3–5 practical actions.
Each action should begin with a verb.
Examples:
- Review...
- Monitor...
- Check...
- Update...
- Ignore...
""".strip()

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content
def generate_thesis_tracker_review(
    positions: List[Dict],
    portfolio_news: Dict[str, List[Dict]],
    market_context: Dict,
    date_label: str,
) -> str:
    """
    Generate a weekly thesis tracker review using Groq.
    """
    client = get_groq_client()

    thesis_context = format_thesis_context(positions)
    news_context = format_news_for_prompt(portfolio_news)
    market_context_text = format_market_context_for_prompt(market_context)

    system_prompt = """
You are an institutional-quality buy-side portfolio thesis tracker.

Your job is to review each portfolio position and determine whether the investment thesis is:
- Strengthening
- Stable
- Weakening
- Broken
- Monitor

You are not writing a generic news summary. You are checking whether the stored thesis is still valid.

Rules:
- Use only the supplied thesis, market context, and news context.
- Do not invent facts.
- Focus on thesis durability, kill criteria, and follow-up actions.
- Be direct and practical.
- If the available news is thin or not thesis-relevant, say so.
- Identify whether any kill criteria appear to be triggered.
- Assign action priority: Low / Medium / High.
- Use polished buy-side investment language.
""".strip()

    user_prompt = f"""
Prepare the Weekly Thesis Tracker Review for {date_label}.

PORTFOLIO THESIS CONTEXT
{thesis_context}

MARKET CONTEXT
{market_context_text}

RECENT PORTFOLIO NEWS
{news_context}

Use this exact structure:

# Weekly Thesis Tracker — {date_label}

## 1. Portfolio-Level Summary
Give 3–5 bullets on the overall state of the portfolio thesis set.

## 2. Thesis Status Dashboard
Create a markdown table with these columns:

| Ticker | Company | Thesis Status | Evidence Quality | Kill Criteria Triggered? | Action Priority | Required Follow-Up |
|---|---|---|---|---|---|---|

Thesis Status must be one of:
- Strengthening
- Stable
- Weakening
- Broken
- Monitor

Evidence Quality must be one of:
- Strong
- Moderate
- Thin
- Poor

Action Priority must be:
- Low
- Medium
- High

## 3. Position-by-Position Review
For every portfolio position, use this format:

### TICKER — Company Name

**Current thesis status:** Strengthening / Stable / Weakening / Broken / Monitor

**What supports the thesis:**  
Explain what supports the stored thesis based on the supplied information.

**What challenges the thesis:**  
Explain what weakens or challenges the stored thesis.

**Kill criteria check:**  
State whether any stored kill criteria appear to be triggered. If no, say so clearly.

**Evidence quality:** Strong / Moderate / Thin / Poor

**Action priority:** Low / Medium / High

**Required follow-up:**  
List practical follow-up actions.

## 4. Kill Criteria Watchlist
List any position where kill criteria may be close to being triggered.
If none, say: "No kill criteria appear to be triggered from the supplied information."

## 5. Portfolio Manager Action List
List 3–7 practical actions.
Each action should start with a verb.
Examples:
- Review...
- Monitor...
- Update...
- Ignore...
- Reassess...
- Prepare...
""".strip()

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content
def format_event_config_for_prompt(event_config: Dict) -> str:
    """
    Convert event calendar config into prompt text.
    """
    macro_events = event_config.get("macro_events", [])
    portfolio_event_rules = event_config.get("portfolio_event_rules", {})

    lines = []

    lines.append("## Macro Events")
    if not macro_events:
        lines.append("- No macro events configured.")
    else:
        for event in macro_events:
            lines.append(
                f"- Date: {event.get('date', 'N/A')} | "
                f"Event: {event.get('event', 'N/A')} | "
                f"Relevance: {event.get('relevance', 'N/A')}"
            )

    lines.append("\n## Portfolio Event Rules")
    if not portfolio_event_rules:
        lines.append("- No portfolio event rules configured.")
    else:
        for ticker, rules in portfolio_event_rules.items():
            lines.append(f"\n### {ticker}")
            watch_for = rules.get("watch_for", [])
            if watch_for:
                for item in watch_for:
                    lines.append(f"- {item}")
            else:
                lines.append("- No watch rules configured.")

    return "\n".join(lines)


def generate_event_calendar_review(
    positions: List[Dict],
    event_config: Dict,
    market_context: Dict,
    date_label: str,
) -> str:
    """
    Generate a weekly portfolio-relevant event calendar using Groq.
    """
    client = get_groq_client()

    thesis_context = format_thesis_context(positions)
    market_context_text = format_market_context_for_prompt(market_context)
    event_context = format_event_config_for_prompt(event_config)

    system_prompt = """
You are an institutional-quality buy-side event calendar analyst.

Your job is to create a weekly event calendar filtered to what matters for the portfolio.

You are not producing a generic calendar. You are identifying:
- macro events that can affect the portfolio
- company-specific catalyst categories to watch
- earnings or update risks that matter to the stored thesis
- action items for the portfolio manager

Rules:
- Use only the supplied portfolio thesis context, market context, and configured event context.
- Do not invent exact earnings dates unless they are supplied.
- If no exact dates are supplied, frame items as "monitor this week" rather than pretending there is a scheduled date.
- Link every event back to the relevant thesis driver, valuation sensitivity, or kill criterion.
- Be practical and concise.
- Use polished buy-side investment language.
""".strip()

    user_prompt = f"""
Prepare the Weekly Event Calendar for {date_label}.

PORTFOLIO THESIS CONTEXT
{thesis_context}

MARKET CONTEXT
{market_context_text}

CONFIGURED EVENT CONTEXT
{event_context}

Use this exact structure:

# Weekly Event Calendar — {date_label}

## 1. Portfolio-Relevant Week Ahead
Give 3–5 bullets on what matters most this week.

## 2. Macro Events to Watch
Create a markdown table:

| Event | Timing | Portfolio Relevance | Affected Holdings | Action Required |
|---|---|---|---|---|

Only include events supplied in the configured event context.

## 3. Position-Specific Catalyst Watch
Create a markdown table:

| Ticker | Company | Catalyst / Watch Item | Thesis Link | Urgency | Follow-Up |
|---|---|---|---|---|---|

Include every portfolio position.

## 4. Valuation and Risk Sensitivities
Explain which holdings are most sensitive to:
- rates
- FX
- commodities
- AI capex / technology cycle
- regulatory risk

## 5. Portfolio Manager Action List
List 3–7 practical actions.
Each action must start with a verb.
Examples:
- Monitor...
- Review...
- Prepare...
- Update...
- Ignore...
- Reassess...

## 6. Data Limitations
State clearly that exact live earnings dates are not yet connected unless supplied in the configured event context.
""".strip()

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content

def generate_market_curator_review(
    positions: List[Dict],
    portfolio_news: Dict[str, List[Dict]],
    market_context: Dict,
    date_label: str,
) -> str:
    """
    Generate an end-of-day market curator note using Groq.
    """
    client = get_groq_client()

    thesis_context = format_thesis_context(positions)
    news_context = format_news_for_prompt(portfolio_news)
    market_context_text = format_market_context_for_prompt(market_context)

    system_prompt = """
You are an institutional-quality end-of-day market curator.

Your job is to tell a portfolio manager what happened today that matters for tomorrow.

You are not writing a generic market recap.
You are filtering the day through the portfolio thesis library.

Rules:
- Filter noise aggressively.
- Distinguish thesis-relevant developments from price/action noise.
- Link developments to stored thesis drivers, kill criteria, or valuation sensitivity.
- Identify what should be acted on tomorrow.
- Identify what should be ignored.
- Do not invent facts outside the supplied thesis, market context, and news context.
- Include source links only from supplied URLs.
- Use polished buy-side investment language.
""".strip()

    user_prompt = f"""
Prepare the Market Curator end-of-day report for {date_label}.

PORTFOLIO THESIS CONTEXT
{thesis_context}

MARKET CONTEXT
{market_context_text}

RECENT PORTFOLIO NEWS
{news_context}

Use this exact structure:

# Market Curator — {date_label}

## 1. What Actually Mattered Today
Give 3–5 bullet points only.
Focus on developments that could affect tomorrow's decisions.

## 2. Portfolio Impact Table
Create a markdown table:

| Ticker | Development | Thesis Impact | Urgency | Action for Tomorrow |
|---|---|---|---|---|

Include every portfolio position.

Thesis Impact must be one of:
- Strengthens
- Weakens
- Neutral
- Monitor

Urgency must be one of:
- Low
- Medium
- High

## 3. Position-by-Position Curator Notes
For every position, use this format:

### TICKER — Company Name

**Today’s relevant development:**  
Summarise what mattered, or say there was no thesis-relevant development.

**Thesis read-through:**  
Explain whether the development changes the thesis, valuation sensitivity, risk profile, or monitoring priority.

**Tomorrow’s action:**  
Give one practical action.

**Source:**  
Include article title and URL if a source was used.

## 4. Noise to Ignore
List headlines, moves, or developments that do not appear thesis-relevant from the supplied information.
If none, say: "No clear noise items identified from the supplied information."

## 5. Risk Flags for Tomorrow
List any risks that should be watched tomorrow.
If none, say: "No urgent risk flags identified for tomorrow."

## 6. Source Links
Create a clean bullet list of source links used:
- TICKER — Article title — URL

Only include URLs supplied in the news context.

## 7. Tomorrow’s Watchlist
List 3–7 practical actions.
Each action must start with a verb.
Examples:
- Monitor...
- Review...
- Check...
- Ignore...
- Prepare...
- Reassess...
""".strip()

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    return completion.choices[0].message.content

def format_single_company_news_for_prompt(articles: List[Dict]) -> str:
    """
    Format recent news for one company or ticker.
    """
    if not articles:
        return "No recent articles found."

    lines = []

    for index, article in enumerate(articles, start=1):
        title = article.get("title") or "No title"
        description = article.get("description") or "No description"
        source = article.get("source") or "Unknown source"
        published_at = article.get("published_at") or "Unknown date"
        url = article.get("url") or "No URL provided"

        lines.append(
            f"""
Article {index}
Title: {title}
Source: {source}
Published: {published_at}
Summary: {description}
URL: {url}
""".strip()
        )

    return "\n\n".join(lines)


def format_company_context_for_prompt(company_context: Dict) -> str:
    """
    Format stored company or candidate context for Deep Digger.
    """
    thesis = company_context.get("investment_thesis", {})
    valuation = company_context.get("valuation", {})
    monitoring = company_context.get("monitoring", {})

    core_drivers = thesis.get("core_drivers", [])
    metrics = thesis.get("key_metrics_to_monitor", [])
    kill_criteria = thesis.get("kill_criteria", [])
    notes = company_context.get("notes", [])

    core_driver_text = "\n".join([f"- {item}" for item in core_drivers]) or "- Not provided"
    metrics_text = "\n".join([f"- {item}" for item in metrics]) or "- Not provided"
    kill_criteria_text = "\n".join([f"- {item}" for item in kill_criteria]) or "- Not provided"
    notes_text = "\n".join([f"- {item}" for item in notes]) or "- Not provided"

    return f"""
Ticker / Search Term: {company_context.get("ticker")}
Company Name: {company_context.get("company_name")}
Asset Type: {company_context.get("asset_type")}
Sector: {company_context.get("sector")}
Position Status: {company_context.get("position_status")}
Portfolio Weight: {company_context.get("portfolio_weight", "N/A")}%
Monitoring Priority: {monitoring.get("overnight_news_priority", "normal")}

Stored One-Line Thesis:
{thesis.get("one_line", "No stored thesis available.")}

Core Drivers:
{core_driver_text}

Key Metrics to Monitor:
{metrics_text}

Kill Criteria:
{kill_criteria_text}

Valuation Reference:
- Bear Case: {valuation.get("bear_case", "N/A")}
- Fair Value: {valuation.get("fair_value", "N/A")}
- Bull Case: {valuation.get("bull_case", "N/A")}
- Required Return Threshold: {valuation.get("required_return_threshold", "N/A")}

Notes:
{notes_text}
""".strip()


def generate_deep_digger_memo(
    company_or_ticker: str,
    company_context: Dict,
    recent_news: List[Dict],
    market_context: Dict,
    date_label: str,
) -> str:
    """
    Generate a full investment memo using Groq.
    """
    client = get_groq_client()

    company_context_text = format_company_context_for_prompt(company_context)
    news_context = format_single_company_news_for_prompt(recent_news)
    market_context_text = format_market_context_for_prompt(market_context)

    system_prompt = """
You are an institutional-quality buy-side equity research analyst.

Your job is to produce a full investment memo for a portfolio manager.

You are not writing generic company description content. You are producing a decision-useful investment memo.

Rules:
- Use only supplied company context, recent news, and market context.
- Do not invent precise financial numbers, valuation multiples, earnings dates, or market data that are not supplied.
- If information is missing, say what must be researched next.
- Distinguish clearly between facts supplied, analytical inference, and areas requiring verification.
- Be practical, investment-focused, and concise.
- Include a balanced bull case and bear case.
- Include red flags and what would change the recommendation.
- If the company is already in the portfolio thesis library, use the stored thesis as the starting point.
- If it is not in the portfolio library, treat it as a new research candidate.
- Use polished buy-side investment language.
""".strip()

    user_prompt = f"""
Prepare a Deep Digger Investment Memo for {company_or_ticker} as of {date_label}.

COMPANY / PORTFOLIO CONTEXT
{company_context_text}

MARKET CONTEXT
{market_context_text}

RECENT NEWS CONTEXT
{news_context}

Use this exact structure:

# Deep Digger Investment Memo — {company_or_ticker} — {date_label}

## 1. Executive Summary
Give 5–7 bullets:
- what the company appears to be
- why it may matter
- initial investment view
- key uncertainties
- whether this is actionable now or needs more work

## 2. Business Model
Explain the likely business model based only on supplied context and news.
If the supplied context is insufficient, say what must be verified.

## 3. Investment Thesis
State the thesis in 3–5 bullets.
If a stored thesis exists, use it.
If no stored thesis exists, propose a provisional thesis clearly labelled as provisional.

## 4. Industry Structure
Discuss the competitive and industry context.
Separate confirmed information from assumptions.

## 5. Moat / Competitive Advantage
Assess possible sources of moat:
- scale
- network effects
- switching costs
- brand
- cost advantage
- regulation
- technology
- data advantage

Mark each as Strong / Moderate / Weak / Unknown.

## 6. Financial Quality
Assess what needs to be reviewed:
- revenue growth
- margin structure
- cash conversion
- balance sheet
- reinvestment needs
- cyclicality
- capital intensity

Do not invent financial figures.

## 7. Valuation Framework
Create a valuation framework, not a fake valuation.
Include:
- key valuation drivers
- suitable valuation methods
- what data is needed for a DCF
- what data is needed for comparable valuation
- bear/base/bull valuation logic

## 8. Bull Case
Give the strongest investment case.

## 9. Bear Case
Give the strongest short / avoid case.

## 10. Key Risks
List the major risks and why they matter.

## 11. Red Flags
List specific red flags to investigate.
Include accounting, leverage, governance, customer concentration, regulation, and competitive risk where relevant.

## 12. Catalysts
List possible catalysts:
- earnings
- product launches
- macro changes
- regulatory events
- margin inflection
- capital allocation
- valuation reset

## 13. Position Sizing View
Give a provisional sizing view:
- Avoid
- Watchlist only
- Starter position
- Core position candidate

Explain what evidence is required before increasing size.

## 14. Final Recommendation
Choose one:
- Avoid for now
- Add to watchlist
- Begin deeper research
- Starter position candidate
- Existing position: maintain
- Existing position: reassess

## 15. Source Links
List all source URLs supplied in the recent news context.
Format:
- Article title — URL

## 16. Research Gaps
List the exact information still required before making a real investment decision.
""".strip()

    completion = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.25,
    )

    return completion.choices[0].message.content