"""Canonical financial statement line items the extraction pipeline looks for.

Doubles as the seed data for the `data_dictionary` table (spec 1.6 — metadata
& lineage: field name, type, description, source, owner).
"""

REQUIRED_FIELDS = {
    "revenue",
    "net_income",
    "total_assets",
    "total_liabilities",
    "total_equity",
}

CANONICAL_FIELDS = [
    {
        "field_name": "revenue",
        "type": "currency",
        "description": "Total revenue / net sales for the period.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "cost_of_goods_sold",
        "type": "currency",
        "description": "Cost of goods sold / cost of revenue.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "gross_profit",
        "type": "currency",
        "description": "Revenue minus cost of goods sold.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "operating_expenses",
        "type": "currency",
        "description": "Total operating expenses (SG&A, R&D, etc.).",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "operating_income",
        "type": "currency",
        "description": "Income from operations before interest and taxes.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "net_income",
        "type": "currency",
        "description": "Bottom-line net income / net earnings for the period.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "total_assets",
        "type": "currency",
        "description": "Total assets on the balance sheet.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "total_liabilities",
        "type": "currency",
        "description": "Total liabilities on the balance sheet.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "total_equity",
        "type": "currency",
        "description": "Total shareholders' / stockholders' equity.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "cash_and_equivalents",
        "type": "currency",
        "description": "Cash and cash equivalents on the balance sheet.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "total_current_assets",
        "type": "currency",
        "description": "Total current assets.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "total_current_liabilities",
        "type": "currency",
        "description": "Total current liabilities.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "operating_cash_flow",
        "type": "currency",
        "description": "Net cash provided by operating activities.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "eps_diluted",
        "type": "decimal",
        "description": "Diluted earnings per share.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "shares_outstanding",
        "type": "integer",
        "description": "Weighted average diluted shares outstanding.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "inventory",
        "type": "currency",
        "description": "Inventory on the balance sheet - used to compute the quick ratio (excluded from current assets).",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
    {
        "field_name": "interest_expense",
        "type": "currency",
        "description": "Interest expense for the period - used for the interest coverage ratio.",
        "source": "AI extraction (Claude, cited from source PDF)",
        "owner": "finance-data-team",
    },
]

FIELD_NAMES = [f["field_name"] for f in CANONICAL_FIELDS]

# The assurance-tier reference copy (CSRS 4200 / CSRE 2400 / audit) is display-only
# and lives solely in frontend/src/assuranceStandards.ts. It is deliberately NOT
# duplicated here: two copies of regulatory descriptions can drift, and only the
# UI ever renders them. The backend just stores the classified level string.

VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "JPY", "CHF", "AUD"}
