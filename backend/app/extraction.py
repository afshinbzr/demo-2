"""AI extraction pipeline: send a PDF to Claude with native Citations enabled,
parse the fixed-format response into structured fields, each backed by a
real (API-verified) quote + page number from the source document.

Citations are incompatible with structured JSON output (`output_config.format`)
on the Messages API, so instead of asking for JSON we ask for one fact per
line in a fixed `FIELD: value | unit | period` format and parse it ourselves.

Citations only attach to text the API can match verbatim against the source
document. A normalized number like "160223000" (no commas, thousands
multiplied out) usually does NOT appear literally in the PDF, so it never
gets cited. To keep real grounding, each FIELD line is followed by a QUOTE
line asking Claude to reproduce the exact source text (with its original
formatting) - citations attach to *that* line, and we associate them back
with the preceding FIELD line. The same trick grounds the assurance-level
classification (ASSURANCE_QUOTE).
"""

import base64
import logging
import os
import re
from dataclasses import dataclass, field

import anthropic

from .data_dictionary import FIELD_NAMES

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"

HEADER_KEYS = (
    "COMPANY", "STATEMENT_TYPE", "FISCAL_PERIOD", "CURRENCY",
    "PERIOD_TYPE", "PERIODS_COVERED", "ASSURANCE_LEVEL", "ASSURANCE_STANDARD",
)
HEADER_RE = re.compile(r"^(" + "|".join(HEADER_KEYS) + r"):\s*(.+)$")
# Tolerate an occasional stray "FIELD_NAME: " / "FIELD: " prefix the model
# sometimes adds despite the prompt - defensive parsing, not the primary fix.
FIELD_LINE_RE = re.compile(
    r"^(?:FIELD(?:_NAME)?:\s*)?([A-Z_]+):\s*([-0-9.,]+)\s*\|\s*([A-Za-z]{0,4})\s*\|\s*(.*)$"
)
QUOTE_LINE_RE = re.compile(r"^QUOTE:\s*(.*)$")
ASSURANCE_QUOTE_LINE_RE = re.compile(r"^ASSURANCE_QUOTE:\s*(.*)$")

SYSTEM_PROMPT = """You are a financial-statement data extraction analyst supporting a commercial \
lender's credit evaluation. You will be given a financial statement as a PDF. Extract the data \
precisely and output ONLY in the exact format specified below - no other commentary.

First, these header lines, one fact per line:
COMPANY: <company name>
STATEMENT_TYPE: <one of: income_statement, balance_sheet, cash_flow, other>
FISCAL_PERIOD: <the most recent/primary period, e.g. FY2024, Q3 2024>
CURRENCY: <3-letter ISO currency code, e.g. USD>
PERIOD_TYPE: <single_period if only one period's figures are presented, multi_year if the \
statement shows two or more periods/years side by side for comparison>
PERIODS_COVERED: <comma-separated list of every distinct period/year presented, most recent \
first, e.g. "FY2026, FY2025">
ASSURANCE_LEVEL: <one of: compilation, review, audit, none, unknown - see rules below>
ASSURANCE_STANDARD: <the standard named in the accountant's report, e.g. "CSRS 4200", \
"CSRE 2400", or the audit standard named; "n/a" if ASSURANCE_LEVEL is none or unknown>

Determining ASSURANCE_LEVEL - read the accountant's report / notice to reader / auditor's \
report page (if one exists) and classify by what it actually says, not by guessing from the \
company's size:
- "compilation": an accountant's Notice to Reader or compilation report is attached, disclaiming \
any assurance (governed in Canada by CSRS 4200, which replaced old Section 9200).
- "review": a review engagement report is attached, describing limited assurance (governed in \
Canada by CSRE 2400).
- "audit": an independent auditor's report is attached expressing an opinion (full/reasonable \
assurance).
- "none": the statements are explicitly labelled "unaudited" or "management-prepared" with NO \
accountant's report of any kind attached (common for internal or interim statements).
- "unknown": you cannot tell either way from the document.
Then output one more line:
ASSURANCE_QUOTE: "<verbatim excerpt from the accountant's report/notice, or from an "unaudited" \
label, that supports your ASSURANCE_LEVEL classification - copied character-for-character>"
If ASSURANCE_LEVEL is "unknown", write ASSURANCE_QUOTE: "n/a".

Then, for each financial fact you can find, output exactly two lines. Replace "REVENUE" below \
with the actual field name for that fact (chosen from the list further down) - the two lines \
must start with the field name itself, e.g. "REVENUE: 45200000 | USD | FY2024", never with the \
literal words "FIELD_NAME" or "FIELD":
REVENUE: numeric_value | unit | period
QUOTE: "<verbatim excerpt copied character-for-character from the document>"

If PERIOD_TYPE is multi_year, output the field once per period found (most recent period \
first), so trend comparisons are possible - e.g. two REVENUE lines, one per year, each with its \
own period and QUOTE. If PERIOD_TYPE is single_period, output each field only once.

Use ONLY these field names (uppercase, only the ones you can actually find - skip any not \
present in the document, do not guess or invent a value):
{fields}

Rules:
- One fact per field-name/QUOTE pair, and each fact must be a number you can point to \
verbatim in the source document via its QUOTE line - this lets us verify it.
- numeric_value: plain number, no currency symbols, no commas, scaled to actual units even if \
the statement is presented "in thousands" or "in millions" (e.g. 45200000, not $45.2M, 45,200, or 45,200,000).
- Every QUOTE (including ASSURANCE_QUOTE) must be an EXACT, character-for-character copy of a \
short contiguous span of the document's own text - as if you selected it with a mouse and \
copy-pasted it. It must be wrapped in double quotes. Do not paraphrase, reformat, reorder \
words, translate scale, drop or add footnote markers, or otherwise alter it in any way - copy \
it exactly as printed. Keep each field QUOTE short (just the line item label and its number, \
e.g. "Net sales   160,223"), not a whole sentence.
- unit is the currency code repeated, or "shares" for share counts, or blank for per-share/ratio figures.
- period is the fiscal period this specific number applies to.

Next, output one line "SUMMARY:" followed by a detailed, multi-paragraph narrative written for \
a lender evaluating this business for credit - cover: profitability (margins, trend if \
multi-year), liquidity, leverage/solvency, cash flow adequacy, and any red flags a lender should \
know about (e.g. thin margins, declining trend, high leverage, going-concern language, related-\
party transactions). Be specific and cite the actual numbers. If PERIOD_TYPE is multi_year, \
explicitly discuss the trend between periods. End with a one-paragraph overall assessment.

Finally, output one line "NOTES:" followed by a bulleted list of any judgment calls, ambiguous \
labels, assumptions, or things a human reviewer should double check (e.g. "no separate COGS line \
item existed; used Total Cost of Revenue instead"). If there is nothing to note, write "NOTES:" \
followed by "- none".
""".format(fields=", ".join(f.upper() for f in FIELD_NAMES))


@dataclass
class ParsedCitation:
    cited_text: str
    page_number: int | None
    # True: API-matched this quote against the actual source text. False: the
    # model's self-reported quote, kept for manual verification - citation
    # attachment is inherently stochastic (see module docstring).
    # Defaults True since `_block_citations` builds intermediate (unused-flag)
    # entries too - only the final per-field citations set this explicitly.
    verified: bool = True


@dataclass
class ParsedField:
    field_name: str
    raw_label: str
    value: float
    unit: str | None
    period: str | None
    citations: list[ParsedCitation] = field(default_factory=list)


@dataclass
class ExtractionResult:
    company_name: str | None
    statement_type: str | None
    fiscal_period: str | None
    currency: str | None
    period_type: str | None
    periods_covered: str | None
    assurance_level: str | None
    assurance_standard: str | None
    assurance_citation: ParsedCitation | None
    fields: list[ParsedField]
    summary: str
    notes: str
    raw_text: str
    error: str | None = None


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Set it in the environment before uploading statements."
        )
    return anthropic.Anthropic(api_key=api_key)


def _block_citations(block) -> list[ParsedCitation]:
    raw_citations = getattr(block, "citations", None) or []
    out: list[ParsedCitation] = []
    for c in raw_citations:
        page = getattr(c, "start_page_number", None)
        cited_text = getattr(c, "cited_text", "") or ""
        out.append(ParsedCitation(cited_text=cited_text, page_number=page))
    return out


def _citations_overlapping(
    line_start: int, line_end: int, block_spans: list[tuple[int, int, list[ParsedCitation]]]
) -> list[ParsedCitation]:
    """Citations from any block whose text overlaps this line's character range.

    `citation.cited_text` is the *source-document* passage backing the claim
    (often a whole page) - not a short excerpt of the model's own output - so
    it can't be substring-matched against the line. Citation-bearing blocks
    are narrowly scoped to just the quoted span by construction (see the
    debug output that motivated this), so plain offset overlap is precise
    without an additional text filter.
    """
    matches: list[ParsedCitation] = []
    for b_start, b_end, citations in block_spans:
        if b_start >= line_end or b_end <= line_start:
            continue
        matches.extend(citations)
    return matches


def _resolve_quote_citations(
    short_quote: str, line_start: int, line_end: int,
    block_spans: list[tuple[int, int, list[ParsedCitation]]],
) -> list[ParsedCitation]:
    """Pair a parsed QUOTE line's text with any API citations landing on it,
    deduped by page. Falls back to a single unverified entry (page unknown)
    so the model's claimed quote is never silently discarded - citation
    attachment is stochastic (see module docstring)."""
    api_citations = _citations_overlapping(line_start, line_end, block_spans)
    pages_seen: set[int | None] = set()
    citations: list[ParsedCitation] = []
    for c in api_citations:
        if c.page_number in pages_seen:
            continue
        pages_seen.add(c.page_number)
        citations.append(ParsedCitation(cited_text=short_quote, page_number=c.page_number, verified=True))
    if not citations and short_quote:
        citations.append(ParsedCitation(cited_text=short_quote, page_number=None, verified=False))
    return citations


def extract_statement(pdf_bytes: bytes) -> ExtractionResult:
    client = _get_client()
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    # Streaming (rather than max_tokens=24000 in one shot) avoids the SDK's
    # non-streaming timeout guard for large outputs - the detailed lender
    # summary plus multi-year field repeats can run long.
    with client.messages.stream(
        model=MODEL,
        max_tokens=24000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64,
                        },
                        "citations": {"enabled": True},
                    },
                    {
                        "type": "text",
                        "text": "Extract the financial data from this statement following the format exactly.",
                    },
                ],
            }
        ],
    ) as stream:
        response = stream.get_final_message()

    # Reconstruct the full response text with an offset->citations map. Blocks
    # must be concatenated with NO separator - Anthropic splits one continuous
    # stream into blocks at citation boundaries, not at line breaks, so
    # inserting anything between them would desync every offset after the
    # first split.
    full_text_parts: list[str] = []
    block_spans: list[tuple[int, int, list[ParsedCitation]]] = []
    offset = 0
    for block in response.content:
        if getattr(block, "type", None) != "text":
            continue
        text = block.text or ""
        block_spans.append((offset, offset + len(text), _block_citations(block)))
        full_text_parts.append(text)
        offset += len(text)
    full_text = "".join(full_text_parts)

    valid_field_names = {f.upper() for f in FIELD_NAMES}

    header_values: dict[str, str] = {}
    summary_lines: list[str] = []
    notes_lines: list[str] = []
    section = "header"  # header -> facts -> summary -> notes

    pending_field: dict | None = None
    pending_assurance = False  # True while awaiting ASSURANCE_QUOTE line
    assurance_citation: ParsedCitation | None = None
    parsed_fields: list[ParsedField] = []

    line_start = 0
    for raw_line in full_text.splitlines(keepends=True):
        this_start = line_start
        this_end = line_start + len(raw_line)
        line_start = this_end
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("SUMMARY:"):
            section = "summary"
            remainder = line[len("SUMMARY:"):].strip()
            if remainder:
                summary_lines.append(remainder)
            continue

        if line.upper().startswith("NOTES:"):
            section = "notes"
            remainder = line[len("NOTES:"):].strip()
            if remainder:
                notes_lines.append(remainder)
            continue

        if section == "notes":
            notes_lines.append(line)
            continue

        if section == "summary":
            summary_lines.append(line)
            continue

        # section in {"header", "facts"} from here on
        assurance_quote_match = ASSURANCE_QUOTE_LINE_RE.match(line)
        if assurance_quote_match and pending_assurance:
            short_quote = assurance_quote_match.group(1).strip().strip('"')
            if short_quote and short_quote.lower() != "n/a":
                citations = _resolve_quote_citations(short_quote, this_start, this_end, block_spans)
                assurance_citation = citations[0] if citations else None
            pending_assurance = False
            continue

        header_match = HEADER_RE.match(line)
        if header_match:
            key, val = header_match.group(1), header_match.group(2).strip()
            header_values[key] = val
            if key == "ASSURANCE_STANDARD":
                pending_assurance = True
                section = "facts"
            continue

        quote_match = QUOTE_LINE_RE.match(line)
        if quote_match and pending_field:
            short_quote = quote_match.group(1).strip().strip('"')
            citations = _resolve_quote_citations(short_quote, this_start, this_end, block_spans)
            parsed_fields.append(
                ParsedField(
                    field_name=pending_field["field_name"],
                    raw_label=pending_field["raw_label"],
                    value=pending_field["value"],
                    unit=pending_field["unit"],
                    period=pending_field["period"],
                    citations=citations,
                )
            )
            pending_field = None
            continue

        field_match = FIELD_LINE_RE.match(line)
        if field_match:
            section = "facts"
            # A field with no QUOTE line (model skipped it) is still recorded,
            # just with no citation - lower confidence, flagged for review.
            if pending_field:
                parsed_fields.append(ParsedField(**pending_field))
                pending_field = None

            name, value_str, unit, period = field_match.groups()
            if name not in valid_field_names:
                continue
            try:
                value = float(value_str.replace(",", ""))
            except ValueError:
                continue

            pending_field = {
                "field_name": name.lower(),
                "raw_label": name.replace("_", " ").title(),
                "value": value,
                "unit": unit or header_values.get("CURRENCY"),
                "period": period.strip() or header_values.get("FISCAL_PERIOD"),
            }

    if pending_field:
        parsed_fields.append(ParsedField(**pending_field))

    valid_period_types = {"single_period", "multi_year"}
    valid_assurance_levels = {"compilation", "review", "audit", "none"}
    period_type = (header_values.get("PERIOD_TYPE") or "").strip().lower()
    assurance_level = (header_values.get("ASSURANCE_LEVEL") or "").strip().lower()

    return ExtractionResult(
        company_name=header_values.get("COMPANY"),
        statement_type=header_values.get("STATEMENT_TYPE"),
        fiscal_period=header_values.get("FISCAL_PERIOD"),
        currency=header_values.get("CURRENCY"),
        period_type=period_type if period_type in valid_period_types else "unknown",
        periods_covered=header_values.get("PERIODS_COVERED"),
        assurance_level=assurance_level if assurance_level in valid_assurance_levels else "unknown",
        assurance_standard=header_values.get("ASSURANCE_STANDARD"),
        assurance_citation=assurance_citation,
        fields=parsed_fields,
        summary="\n".join(summary_lines) if summary_lines else "",
        notes="\n".join(notes_lines) if notes_lines else "",
        raw_text=full_text,
    )
