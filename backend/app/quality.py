"""Deterministic data-quality rule engine (spec section 2) + composite scoring.

Runs after AI extraction, on every statement. Never silently drops bad data:
failures are written to `quarantine` with a reason code (spec 2.7) and the
record is still stored, flagged for human review.
"""

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .data_dictionary import REQUIRED_FIELDS, VALID_CURRENCIES
from .models import LineItem, Quarantine, Statement

# Real statements label periods in many valid ways - "FY2026", "Q3 2024",
# "H1 2026", "As at June 26, 2026", "Six months ended June 27, 2025",
# "Exercice clos le 31 décembre 2025". The check that actually matters for a
# credit analyst is that the period identifies a *year*; anything with a
# 4-digit year is accepted. A stricter pattern flooded the quarantine queue
# with false positives on perfectly good multi-year statements.
PERIOD_RE = re.compile(r"(19|20)\d{2}")

# Fields that should never be negative in a well-formed statement.
NON_NEGATIVE_FIELDS = {
    "revenue",
    "total_assets",
    "total_liabilities",
    "total_equity",
    "cash_and_equivalents",
    "total_current_assets",
    "total_current_liabilities",
    "shares_outstanding",
    "operating_expenses",
    "cost_of_goods_sold",
}

BALANCE_SHEET_TOLERANCE = 0.05  # 5%


@dataclass
class QualityScores:
    completeness: float
    validity: float
    consistency: float
    uniqueness: float
    citation_coverage: float

    @property
    def composite(self) -> float:
        return round(
            0.25 * self.completeness
            + 0.20 * self.validity
            + 0.25 * self.consistency
            + 0.10 * self.uniqueness
            + 0.20 * self.citation_coverage,
            1,
        )


def _add_quarantine(db: Session, statement: Statement, reason_code: str, detail: str,
                     line_item: LineItem | None = None) -> None:
    db.add(
        Quarantine(
            statement_id=statement.id,
            line_item_id=line_item.id if line_item else None,
            reason_code=reason_code,
            detail=detail,
        )
    )


def run_quality_checks(
    db: Session, statement: Statement, line_items: list[LineItem], record_quarantine: bool = True
) -> QualityScores:
    """Compute the 5 composite-score dimensions. When `record_quarantine` is True
    (initial processing only), also writes quarantine rows for failures. Score
    recomputation after a human resolves a quarantine item passes False so the
    same condition isn't immediately re-flagged."""

    def maybe_quarantine(reason_code: str, detail: str, line_item: LineItem | None = None) -> None:
        if record_quarantine:
            _add_quarantine(db, statement, reason_code, detail, line_item=line_item)

    active_items = [li for li in line_items if not li.is_deleted]
    # First occurrence per field = the most recent period (the extraction
    # prompt emits current period before comparatives). Cross-field checks
    # below must compare within ONE period - a dict built last-wins would
    # silently mix this year's assets with last year's equity on a
    # multi-year statement.
    by_field: dict[str, LineItem] = {}
    for li in active_items:
        by_field.setdefault(li.field_name, li)

    # --- 0. Unit scale ambiguity (spec: inconsistent units can distort an
    # entire credit analysis) - the AI itself flagged uncertainty reconciling
    # a scale mismatch (e.g. one section "in thousands", another in whole
    # dollars) rather than silently guessing.
    if statement.unit_scale_uncertain:
        maybe_quarantine(
            "unit_scale_uncertain",
            statement.unit_scale_note or "The AI was not confident about the reporting unit scale "
            "(raw dollars vs. thousands vs. millions) used in this document.",
        )

    # --- 1. Completeness ---
    present_required = REQUIRED_FIELDS & set(by_field.keys())
    missing_required = REQUIRED_FIELDS - set(by_field.keys())
    for missing in missing_required:
        maybe_quarantine(
            "missing_required_field",
            f"Required field '{missing}' was not found in the extracted statement.",
        )
    completeness = 100.0 * len(present_required) / len(REQUIRED_FIELDS) if REQUIRED_FIELDS else 100.0

    # --- 2. Validity ---
    validity_checks = 0
    validity_passed = 0

    if statement.currency:
        validity_checks += 1
        if statement.currency.upper() in VALID_CURRENCIES:
            validity_passed += 1
        else:
            maybe_quarantine(
                "invalid_currency",
                f"Currency code '{statement.currency}' is not a recognized ISO code.",
            )

    for li in active_items:
        if li.field_name in NON_NEGATIVE_FIELDS:
            validity_checks += 1
            if li.value is not None and li.value >= 0:
                validity_passed += 1
            else:
                maybe_quarantine(
                    "invalid_value_range",
                    f"Field '{li.field_name}' has a negative value ({li.value}), which is invalid for this field.",
                    line_item=li,
                )
        if li.period:
            validity_checks += 1
            if PERIOD_RE.search(li.period.strip()):
                validity_passed += 1
            else:
                maybe_quarantine(
                    "invalid_period_format",
                    f"Field '{li.field_name}' has a period with no identifiable year: '{li.period}'.",
                    line_item=li,
                )

    validity = 100.0 * validity_passed / validity_checks if validity_checks else 100.0

    # --- 3. Uniqueness ---
    duplicate = None
    if statement.company_name and statement.fiscal_period:
        duplicate = (
            db.query(Statement)
            .filter(
                Statement.id != statement.id,
                Statement.is_deleted.is_(False),
                Statement.company_name.isnot(None),
                Statement.company_name.ilike(statement.company_name.strip()),
                Statement.fiscal_period.isnot(None),
                Statement.fiscal_period.ilike(statement.fiscal_period.strip()),
            )
            .first()
        )
    if duplicate:
        maybe_quarantine(
            "possible_duplicate",
            f"Statement #{duplicate.id} ('{duplicate.filename}') already covers "
            f"{statement.company_name} / {statement.fiscal_period}.",
        )
    uniqueness = 50.0 if duplicate else 100.0

    # --- 4. Consistency ---
    consistency = 100.0
    assets = by_field.get("total_assets")
    liabilities = by_field.get("total_liabilities")
    equity = by_field.get("total_equity")
    if assets and liabilities and equity and assets.value:
        diff = abs(assets.value - (liabilities.value + equity.value))
        relative_error = diff / abs(assets.value) if assets.value else 0
        if relative_error > BALANCE_SHEET_TOLERANCE:
            maybe_quarantine(
                "balance_sheet_mismatch",
                f"Assets ({assets.value:,.0f}) do not equal Liabilities + Equity "
                f"({liabilities.value + equity.value:,.0f}); {relative_error:.1%} mismatch.",
            )
            consistency = max(0.0, 100.0 - relative_error * 100)

    # --- 5. Accuracy / statistical outliers — flag, never auto-reject (spec 2.5) ---
    revenue = by_field.get("revenue")
    net_income = by_field.get("net_income")
    if revenue and net_income and revenue.value:
        if abs(net_income.value) > abs(revenue.value):
            net_income.is_outlier = True
            maybe_quarantine(
                "statistical_outlier",
                f"Net income ({net_income.value:,.0f}) exceeds total revenue "
                f"({revenue.value:,.0f}) in magnitude — unusual, please verify.",
                line_item=net_income,
            )
    gross_profit = by_field.get("gross_profit")
    if revenue and gross_profit and revenue.value and gross_profit.value > revenue.value:
        gross_profit.is_outlier = True
        maybe_quarantine(
            "statistical_outlier",
            f"Gross profit ({gross_profit.value:,.0f}) exceeds revenue "
            f"({revenue.value:,.0f}) — should not be possible, please verify.",
            line_item=gross_profit,
        )

    # --- 6. Citation coverage (reliability signal) ---
    # Only *verified* citations (matched by the API against the actual source
    # text) count toward reliability - an unverified self-reported quote is
    # still shown to the human for manual checking, but doesn't count as
    # "confirmed grounded" since citation attachment is stochastic (see
    # extraction.py). Confidence follows the same distinction.
    numeric_items = active_items
    verified_items = [li for li in numeric_items if any(c.verified for c in li.citations)]
    citation_coverage = (
        100.0 * len(verified_items) / len(numeric_items) if numeric_items else 0.0
    )
    for li in numeric_items:
        if any(c.verified for c in li.citations):
            li.confidence = "high"
        elif li.citations:
            li.confidence = "medium"
        else:
            li.confidence = "low"

    return QualityScores(
        completeness=round(completeness, 1),
        validity=round(validity, 1),
        consistency=round(consistency, 1),
        uniqueness=round(uniqueness, 1),
        citation_coverage=round(citation_coverage, 1),
    )
