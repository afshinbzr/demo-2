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
with the preceding FIELD line.
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

HEADER_RE = re.compile(r"^(COMPANY|STATEMENT_TYPE|FISCAL_PERIOD|CURRENCY):\s*(.+)$")
# Tolerate an occasional stray "FIELD_NAME: " / "FIELD: " prefix the model
# sometimes adds despite the prompt - defensive parsing, not the primary fix.
FIELD_LINE_RE = re.compile(
    r"^(?:FIELD(?:_NAME)?:\s*)?([A-Z_]+):\s*([-0-9.,]+)\s*\|\s*([A-Za-z]{0,4})\s*\|\s*(.*)$"
)
QUOTE_LINE_RE = re.compile(r"^QUOTE:\s*(.*)$")

SYSTEM_PROMPT = """You are a financial-statement data extraction analyst. You will be given \
a financial statement as a PDF. Extract the data precisely and output ONLY in the exact \
format specified below - no other commentary.

First, four header lines, one fact per line:
COMPANY: <company name>
STATEMENT_TYPE: <one of: income_statement, balance_sheet, cash_flow, other>
FISCAL_PERIOD: <e.g. FY2024, Q3 2024>
CURRENCY: <3-letter ISO currency code, e.g. USD>

Then, for each financial fact you can find, output exactly two lines. Replace "REVENUE" below \
with the actual field name for that fact (chosen from the list further down) - the two lines \
must start with the field name itself, e.g. "REVENUE: 45200000 | USD | FY2024", never with the \
literal words "FIELD_NAME" or "FIELD":
REVENUE: numeric_value | unit | period
QUOTE: "<verbatim excerpt copied character-for-character from the document>"

Use ONLY these field names (uppercase, only the ones you can actually find - skip any not \
present in the document, do not guess or invent a value):
{fields}

Rules:
- One fact per field-name/QUOTE pair, and each fact must be a number you can point to \
verbatim in the source document via its QUOTE line - this lets us verify it.
- numeric_value: plain number, no currency symbols, no commas, scaled to actual units even if \
the statement is presented "in thousands" or "in millions" (e.g. 45200000, not $45.2M, 45,200, or 45,200,000).
- The QUOTE must be an EXACT, character-for-character copy of a short contiguous span of the \
document's own text - as if you selected it with a mouse and copy-pasted it. It must be wrapped \
in double quotes. Do not paraphrase, reformat, reorder words, translate scale, drop or add \
footnote markers, or otherwise alter it in any way - copy it exactly as printed, including its \
original commas and currency symbols. Keep each quote short (just the line item label and its \
number, e.g. "Net sales   160,223"), not a whole sentence.
- unit is the currency code repeated, or "shares" for share counts, or blank for per-share/ratio figures.
- period is the fiscal period this specific number applies to (may differ per line for multi-period statements - \
if the statement shows prior-year comparatives, use only the most recent period's figures).

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
    # attachment is inherently stochastic (see extract_statement docstring).
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
    fields: list[ParsedField]
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


def extract_statement(pdf_bytes: bytes) -> ExtractionResult:
    client = _get_client()
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
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
    )

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

    company_name = statement_type = fiscal_period = currency = None
    notes_lines: list[str] = []
    in_notes = False

    # (field_name, raw_label, value, unit, period) awaiting its QUOTE line.
    pending_field: dict | None = None
    parsed_fields: list[ParsedField] = []

    line_start = 0
    for raw_line in full_text.splitlines(keepends=True):
        this_start = line_start
        this_end = line_start + len(raw_line)
        line_start = this_end
        line = raw_line.strip()
        if not line:
            continue

        if line.upper().startswith("NOTES:"):
            in_notes = True
            remainder = line[len("NOTES:"):].strip()
            if remainder:
                notes_lines.append(remainder)
            continue

        if in_notes:
            notes_lines.append(line)
            continue

        header_match = HEADER_RE.match(line)
        if header_match:
            key, val = header_match.group(1), header_match.group(2).strip()
            if key == "COMPANY":
                company_name = val
            elif key == "STATEMENT_TYPE":
                statement_type = val
            elif key == "FISCAL_PERIOD":
                fiscal_period = val
            elif key == "CURRENCY":
                currency = val
            continue

        quote_match = QUOTE_LINE_RE.match(line)
        if quote_match and pending_field:
            short_quote = quote_match.group(1).strip().strip('"')
            api_citations = _citations_overlapping(this_start, this_end, block_spans)
            # Display the model's own short excerpt (verified below), not the
            # API's `cited_text` - that field is the whole source page/passage
            # backing the claim, not something short enough to show as a "quote".
            pages_seen: set[int | None] = set()
            citations: list[ParsedCitation] = []
            for c in api_citations:
                if c.page_number in pages_seen:
                    continue
                pages_seen.add(c.page_number)
                citations.append(
                    ParsedCitation(cited_text=short_quote, page_number=c.page_number, verified=True)
                )
            if not citations and short_quote:
                # The API didn't attach a citation to this quote on this run
                # (citation attachment is stochastic - see module docstring).
                # Keep the model's own claimed quote anyway, clearly marked
                # unverified, rather than discarding it - the human can still
                # search the PDF for it.
                citations.append(ParsedCitation(cited_text=short_quote, page_number=None, verified=False))

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
            # A field with no QUOTE line (model skipped it) is still recorded,
            # just with no citation - lower confidence, flagged for review.
            if pending_field:
                parsed_fields.append(
                    ParsedField(
                        field_name=pending_field["field_name"],
                        raw_label=pending_field["raw_label"],
                        value=pending_field["value"],
                        unit=pending_field["unit"],
                        period=pending_field["period"],
                    )
                )
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
                "unit": unit or currency,
                "period": period.strip() or fiscal_period,
            }

    if pending_field:
        parsed_fields.append(
            ParsedField(
                field_name=pending_field["field_name"],
                raw_label=pending_field["raw_label"],
                value=pending_field["value"],
                unit=pending_field["unit"],
                period=pending_field["period"],
            )
        )

    return ExtractionResult(
        company_name=company_name,
        statement_type=statement_type,
        fiscal_period=fiscal_period,
        currency=currency,
        fields=parsed_fields,
        notes="\n".join(notes_lines) if notes_lines else "",
        raw_text=full_text,
    )
