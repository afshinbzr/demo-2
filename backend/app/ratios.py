"""Standard commercial-credit-analysis ratios, computed deterministically from
extracted line items (never asked of the LLM - arithmetic belongs in code).

These are general, widely-used lending ratios (the kind any commercial
lender - including BDC - looks at), NOT a reproduction of any lender's
actual proprietary underwriting scorecard, which isn't published and this
app has no access to. Flag thresholds are common rules of thumb and vary a
lot by industry and facility type in real underwriting - shown for
orientation, not as a pass/fail verdict.
"""

from dataclasses import asdict, dataclass

from .models import LineItem


@dataclass
class Ratio:
    key: str
    label: str
    category: str  # liquidity | leverage | profitability | coverage
    value: float | None
    unit: str  # ratio | percent | currency
    formula: str
    flag: str | None  # good | warning | critical | None (can't be computed)
    note: str


def _pick_latest(by_field: dict[str, LineItem], name: str) -> float | None:
    li = by_field.get(name)
    return li.value if li else None


def _flag(value: float | None, good: float, warning: float, higher_is_better: bool = True) -> str | None:
    if value is None:
        return None
    if higher_is_better:
        if value >= good:
            return "good"
        if value >= warning:
            return "warning"
        return "critical"
    else:
        if value <= good:
            return "good"
        if value <= warning:
            return "warning"
        return "critical"


def compute_ratios(line_items: list[LineItem]) -> list[Ratio]:
    """Uses the most-recent period's value for each field (the first
    occurrence per field_name, matching the extraction prompt's convention
    of listing the current period before comparatives)."""
    by_field: dict[str, LineItem] = {}
    for li in line_items:
        if not li.is_deleted:
            by_field.setdefault(li.field_name, li)

    revenue = _pick_latest(by_field, "revenue")
    gross_profit = _pick_latest(by_field, "gross_profit")
    operating_income = _pick_latest(by_field, "operating_income")
    net_income = _pick_latest(by_field, "net_income")
    total_assets = _pick_latest(by_field, "total_assets")
    total_liabilities = _pick_latest(by_field, "total_liabilities")
    total_equity = _pick_latest(by_field, "total_equity")
    current_assets = _pick_latest(by_field, "total_current_assets")
    current_liabilities = _pick_latest(by_field, "total_current_liabilities")
    inventory = _pick_latest(by_field, "inventory")
    interest_expense = _pick_latest(by_field, "interest_expense")

    ratios: list[Ratio] = []

    def safe_div(n: float | None, d: float | None) -> float | None:
        if n is None or d is None or d == 0:
            return None
        return n / d

    current_ratio = safe_div(current_assets, current_liabilities)
    ratios.append(Ratio(
        key="current_ratio", label="Current Ratio", category="liquidity",
        value=round(current_ratio, 2) if current_ratio is not None else None,
        unit="ratio", formula="Total Current Assets / Total Current Liabilities",
        flag=_flag(current_ratio, good=1.5, warning=1.0),
        note="Ability to cover short-term obligations with short-term assets. "
             "Below 1.0 means current liabilities exceed current assets." if current_ratio is not None
             else "Requires total_current_assets and total_current_liabilities.",
    ))

    quick_assets = None if current_assets is None else current_assets - (inventory or 0)
    quick_ratio = safe_div(quick_assets, current_liabilities) if inventory is not None else None
    ratios.append(Ratio(
        key="quick_ratio", label="Quick Ratio", category="liquidity",
        value=round(quick_ratio, 2) if quick_ratio is not None else None,
        unit="ratio", formula="(Total Current Assets - Inventory) / Total Current Liabilities",
        flag=_flag(quick_ratio, good=1.0, warning=0.7),
        note="Liquidity excluding inventory (the least liquid current asset)." if quick_ratio is not None
             else "Requires inventory to be reported separately - not found in this statement.",
    ))

    working_capital = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None else None
    )
    ratios.append(Ratio(
        key="working_capital", label="Working Capital", category="liquidity",
        value=round(working_capital, 0) if working_capital is not None else None,
        unit="currency", formula="Total Current Assets - Total Current Liabilities",
        # None must be tested before the >= comparison - `(None or 0) >= 0` is
        # True, which would paint an uncomputable value green.
        flag=None if working_capital is None else ("good" if working_capital >= 0 else "critical"),
        note="Dollar amount of short-term assets available after covering short-term liabilities."
             if working_capital is not None
             else "Requires total_current_assets and total_current_liabilities.",
    ))

    debt_to_equity = safe_div(total_liabilities, total_equity)
    ratios.append(Ratio(
        key="debt_to_equity", label="Debt-to-Equity", category="leverage",
        value=round(debt_to_equity, 2) if debt_to_equity is not None else None,
        unit="ratio", formula="Total Liabilities / Total Equity",
        flag=_flag(debt_to_equity, good=1.0, warning=2.5, higher_is_better=False),
        note="How leveraged the business is. Typical comfortable ranges vary a lot by "
             "industry - a capital-intensive business normally runs higher.",
    ))

    debt_to_assets = safe_div(total_liabilities, total_assets)
    ratios.append(Ratio(
        key="debt_to_assets", label="Debt-to-Assets", category="leverage",
        value=round(debt_to_assets, 2) if debt_to_assets is not None else None,
        unit="ratio", formula="Total Liabilities / Total Assets",
        flag=_flag(debt_to_assets, good=0.5, warning=0.7, higher_is_better=False),
        note="Share of the business's assets financed by debt rather than equity.",
    ))

    gross_margin = safe_div(gross_profit, revenue)
    ratios.append(Ratio(
        key="gross_margin", label="Gross Margin", category="profitability",
        value=round(gross_margin * 100, 1) if gross_margin is not None else None,
        unit="percent", formula="Gross Profit / Revenue",
        flag=_flag(gross_margin * 100 if gross_margin is not None else None, good=30, warning=15),
        note="Profitability before operating expenses.",
    ))

    operating_margin = safe_div(operating_income, revenue)
    ratios.append(Ratio(
        key="operating_margin", label="Operating Margin", category="profitability",
        value=round(operating_margin * 100, 1) if operating_margin is not None else None,
        unit="percent", formula="Operating Income / Revenue",
        flag=_flag(operating_margin * 100 if operating_margin is not None else None, good=10, warning=3),
        note="Profitability from core operations before interest and taxes.",
    ))

    net_margin = safe_div(net_income, revenue)
    ratios.append(Ratio(
        key="net_margin", label="Net Margin", category="profitability",
        value=round(net_margin * 100, 1) if net_margin is not None else None,
        unit="percent", formula="Net Income / Revenue",
        flag=_flag(net_margin * 100 if net_margin is not None else None, good=8, warning=0),
        note="Bottom-line profitability after all expenses, interest, and taxes.",
    ))

    roa = safe_div(net_income, total_assets)
    ratios.append(Ratio(
        key="return_on_assets", label="Return on Assets", category="profitability",
        value=round(roa * 100, 1) if roa is not None else None,
        unit="percent", formula="Net Income / Total Assets",
        flag=_flag(roa * 100 if roa is not None else None, good=5, warning=0),
        note="How efficiently the business turns its asset base into profit.",
    ))

    interest_coverage = safe_div(operating_income, interest_expense) if interest_expense else None
    ratios.append(Ratio(
        key="interest_coverage", label="Interest Coverage", category="coverage",
        value=round(interest_coverage, 2) if interest_coverage is not None else None,
        unit="ratio", formula="Operating Income / Interest Expense",
        flag=_flag(interest_coverage, good=3.0, warning=1.5),
        note="How many times over the business can cover its interest expense from "
             "operating income." if interest_coverage is not None
             else "Requires interest_expense to be reported separately - not found in this statement.",
    ))

    return ratios


def ratios_to_dicts(ratios: list[Ratio]) -> list[dict]:
    return [asdict(r) for r in ratios]
