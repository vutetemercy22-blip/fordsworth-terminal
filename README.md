# Portfolio Intelligence Terminal

A five-agent investment research operating system built in Python and Streamlit.

The system uses a portfolio thesis library, live news, live market context, and Groq AI to generate investment research outputs.

---

## 1. What the system does

The Portfolio Intelligence Terminal has five research agents:

### 1. Morning Analyst
Produces a daily thesis-aware morning briefing.

Output:
- Executive summary
- Market context
- Portfolio-relevant developments
- Thesis impact by position
- Risk flags
- Source links
- Analyst to-do list

### 2. Thesis Tracker
Produces a weekly thesis health review.

Output:
- Thesis status dashboard
- Position-by-position review
- Kill criteria check
- Action priority
- Portfolio manager action list

### 3. Event Calendar
Produces a weekly portfolio-relevant catalyst calendar.

Output:
- Macro events to watch
- Position-specific catalysts
- Valuation sensitivities
- Portfolio manager action list

### 4. Market Curator
Produces an end-of-day relevance filter.

Output:
- What actually mattered today
- Portfolio impact table
- Position-by-position curator notes
- Noise to ignore
- Risk flags for tomorrow
- Tomorrow’s watchlist

### 5. Deep Digger
Produces an on-demand investment memo for any ticker or company.

Output:
- Executive summary
- Business model
- Investment thesis
- Industry structure
- Moat assessment
- Financial quality
- Valuation framework
- Bull case
- Bear case
- Risks
- Red flags
- Catalysts
- Position sizing view
- Final recommendation

---

## 2. Core architecture

```text
Portfolio YAML files
        ↓
NewsAPI company news
        ↓
yfinance market context
        ↓
Groq AI analysis
        ↓
Markdown reports
        ↓
Streamlit dashboard
        ↓
Word exports / Research packs