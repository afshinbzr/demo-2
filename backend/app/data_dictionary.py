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

# The three Canadian assurance-engagement tiers a lender needs to know about
# before trusting a set of financial statements, per CPA Canada standards.
# Shown as reference context next to the AI's classification in the UI.
ASSURANCE_STANDARDS = {
    "compilation": {
        "label": "Compilation (Notice to Reader)",
        "standard": "CSRS 4200",
        "description": (
            "No assurance is provided - the accountant compiles figures from information "
            "the client provides without verifying it. CSRS 4200 (2021) replaced the older "
            "Section 9200 specifically to improve how useful compiled statements are for "
            "third-party users like lenders. This is the cheapest and most common tier for "
            "small businesses."
        ),
    },
    "review": {
        "label": "Review Engagement",
        "standard": "CSRE 2400",
        "description": (
            "Limited assurance - the accountant performs analytical procedures and inquiry, "
            "more than a compilation but well short of an audit."
        ),
    },
    "audit": {
        "label": "Audit",
        "standard": "CAS (Canadian Auditing Standards)",
        "description": (
            "Full (reasonable) assurance - the highest level of verification. Lenders "
            "typically require reviewed statements for credit facilities up to roughly "
            "$5-10M, and audited statements above that."
        ),
    },
    "none": {
        "label": "No assurance engagement (unaudited)",
        "standard": "n/a",
        "description": (
            "The statements are labelled unaudited/management-prepared with no "
            "accountant's compilation, review, or audit report attached - common for "
            "internal or interim statements. Treat with the same caution as a compilation, "
            "or more."
        ),
    },
    "unknown": {
        "label": "Could not be determined",
        "standard": "n/a",
        "description": "No accountant's report or assurance disclaimer was found in the document to classify.",
    },
}

VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "JPY", "CHF", "AUD"}
