from pathlib import Path
from typing import List, Dict, Optional
import re
import yaml

from services.config_service import BASE_DIR, load_settings


def get_portfolio_directory() -> Path:
    settings = load_settings()
    portfolio_path = settings["paths"]["portfolio_dir"]
    portfolio_dir = BASE_DIR / portfolio_path
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    return portfolio_dir


def load_position_file(file_path: Path) -> Dict:
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_all_positions() -> List[Dict]:
    """
    Load all YAML portfolio position files from data/portfolio.
    """
    portfolio_dir = get_portfolio_directory()

    positions = []

    for file_path in sorted(portfolio_dir.glob("*.yaml")):
        position = load_position_file(file_path)
        if position:
            position["_source_file"] = file_path.name
            positions.append(position)

    return positions


def get_position_by_ticker(ticker: str) -> Optional[Dict]:
    """
    Retrieve one position from the thesis library by ticker.
    """
    ticker = ticker.upper().strip()

    for position in load_all_positions():
        if position.get("ticker", "").upper() == ticker:
            return position

    return None


def portfolio_summary() -> Dict:
    positions = load_all_positions()

    total_positions = len(positions)
    total_weight = sum(float(p.get("portfolio_weight", 0) or 0) for p in positions)

    sectors = {}
    for position in positions:
        sector = position.get("sector", "Unknown")
        sectors[sector] = sectors.get(sector, 0) + 1

    return {
        "total_positions": total_positions,
        "total_weight": total_weight,
        "sectors": sectors,
        "positions": positions,
    }


def slugify_ticker(ticker: str) -> str:
    """
    Convert ticker into safe lowercase YAML filename.
    """
    ticker = ticker.strip().lower()
    ticker = re.sub(r"[^a-z0-9_\\-\\.]", "_", ticker)
    return ticker


def position_to_yaml_data(
    ticker: str,
    company_name: str,
    asset_type: str,
    sector: str,
    position_status: str,
    portfolio_weight: float,
    one_line_thesis: str,
    core_drivers: List[str],
    key_metrics_to_monitor: List[str],
    kill_criteria: List[str],
    fair_value,
    bear_case,
    bull_case,
    required_return_threshold,
    overnight_news_priority: str,
    weekly_thesis_review: bool,
    include_in_event_calendar: bool,
    include_in_market_curator: bool,
    notes: List[str],
) -> Dict:
    """
    Build the standard portfolio YAML structure.
    """
    return {
        "ticker": ticker.upper().strip(),
        "company_name": company_name.strip(),
        "asset_type": asset_type.strip(),
        "sector": sector.strip(),
        "position_status": position_status.strip(),
        "portfolio_weight": portfolio_weight,
        "investment_thesis": {
            "one_line": one_line_thesis.strip(),
            "core_drivers": core_drivers,
            "key_metrics_to_monitor": key_metrics_to_monitor,
            "kill_criteria": kill_criteria,
        },
        "valuation": {
            "fair_value": fair_value,
            "bear_case": bear_case,
            "bull_case": bull_case,
            "required_return_threshold": required_return_threshold,
        },
        "monitoring": {
            "overnight_news_priority": overnight_news_priority,
            "weekly_thesis_review": weekly_thesis_review,
            "include_in_event_calendar": include_in_event_calendar,
            "include_in_market_curator": include_in_market_curator,
        },
        "notes": notes,
    }


def save_position(position_data: Dict) -> Path:
    """
    Save one portfolio position as a YAML file in data/portfolio.
    """
    ticker = position_data.get("ticker", "").strip()

    if not ticker:
        raise ValueError("Ticker is required before saving a position.")

    portfolio_dir = get_portfolio_directory()
    filename = f"{slugify_ticker(ticker)}.yaml"
    file_path = portfolio_dir / filename

    with open(file_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(
            position_data,
            file,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )

    return file_path


def delete_position_file(ticker: str) -> bool:
    """
    Delete a position YAML file by ticker.
    """
    ticker_slug = slugify_ticker(ticker)
    file_path = get_portfolio_directory() / f"{ticker_slug}.yaml"

    if file_path.exists():
        file_path.unlink()
        return True

    return False