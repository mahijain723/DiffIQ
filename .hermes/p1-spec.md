Do not include references to ponytail, karpathy, opencode, AI agent, or any internal tooling names in generated code, docstrings, or comments. Use plain professional descriptions only.

# P1: Filing Classification + Section Detection + Text Diff

Implement 3 new modules (classifier, extractor, differ), integrate them into the pipeline, update the dashboard, and add tests.

## Context

Project root: D:\Personal projects\DiffIQ
Existing modules: diffiq/crawler.py, diffiq/pipeline.py, diffiq/db.py, diffiq/schema.py, diffiq/config.py, dashboard/app.py, tests/test_crawler.py, tests/test_db.py
DB tables already exist: stocks, filings, sections, diffs

The pipeline currently crawls BSE -> downloads PDFs -> extracts text via pypdf -> stores in filings (status=READY). Sections and diffs tables exist but are empty.

## Work to do

### 1. diffiq/classifier.py - Filing type classifier

Regex-based classification on filing subject. Types:

- AUDIT_REPORT: audit, auditor
- FINANCIAL_RESULT: result(s), quarter, half year, annual, standalone, consolidated (when with financial/result)
- RPT: related party, rpt
- PROMOTER_CHANGE: promoter, pledge, shareholding pattern
- BOARD_OUTCOME: board meeting, board outcome, board resolution
- ROUTINE: (default - anything that doesn't match above)

Function: `classify_filing(subject: str, raw_text: str | None = None) -> str`
- Match subject against regex patterns (case-insensitive)
- First match wins, default ROUTINE

Function: `classify_pending_filings(conn: sqlite3.Connection) -> int`
- Classify all filings where filing_type IS NULL
- Returns count of updated rows

### 2. diffiq/extractor.py - Section extractor

Splits extracted raw text into logical sections.

Function: `extract_sections(raw_text: str, filing_type: str | None = None) -> list[dict]`
- Returns list of dicts: {header, text, page_num (default 0), section_idx (0-indexed)}
- If filing_type is known, use type-specific section headers
- If unknown/ROUTINE, use generic section headers

**AUDIT_REPORT sections:** Independent Auditor's Report, Opinion, Basis for Opinion, Emphasis of Matter, Key Audit Matters, Management's Responsibility, Other Matter

**FINANCIAL_RESULT sections:** Profit/Loss, Balance Sheet, Statement of, Notes to, Revenue, Expenses, Cash Flow

**RPT sections:** Related Party Transactions/Disclosures, Details of Related Party, Loan to Related

**PROMOTER_CHANGE sections:** Shareholding Pattern, Promoter Holding/Pledge/Shareholding, Statement of Holding/Shares

**Generic headers (fallback):** Split on numbered sections "^\\d+\\.\\s+", split on all-caps lines "^[A-Z][A-Z\\s/]{4,}$", if no splits, return single "Body" section.

Function: `extract_and_store_sections(conn: sqlite3.Connection, filing_id: int, raw_text: str, filing_type: str | None = None) -> list[dict]`
- Calls extract_sections() then insert_sections() from db module

### 3. diffiq/differ.py - Section-aligned text differ

Function: `find_prior_filing(conn, stock_id, filing_type, current_filing_id) -> dict | None`
Function: `align_sections(new_sections, old_sections) -> list[tuple]`
- SequenceMatcher > 0.6 threshold on header + first 200 chars of text
Function: `diff_section(new_text, old_text) -> tuple[str, bool]`
- difflib.unified_diff, changed=True if diff > 100 chars
Function: `run_diffs_for_filing(conn, filing_id, stock_id, filing_type) -> int`
- Orchestrates all of the above, stores via db.insert_diff()

### 4. Pipeline integration

In diffiq/pipeline.py, integrate after text extraction succeeds:
1. Classify: call classifier.classify_pending_filings()
2. Extract sections: call extractor.extract_and_store_sections()
3. Diff: call differ.run_diffs_for_filing()

Add a `sync()` function that processes all existing READY filings through classify -> extract -> differ.

### 5. Dashboard updates (dashboard/app.py)

Add filing detail view:
- Expandable filing rows
- Section-by-section view with expanders
- Show diff status badge per section
- Clean layout matching existing style

### 6. Tests

tests/test_classifier.py: test audit, financial result, rpt, promoter change, board outcome, routine default, case insensitive, empty subject, pending classification

tests/test_extractor.py: test audit sections, financial sections, routine fallback, empty text, store

tests/test_differ.py: test find prior, no prior, section alignment, diff changed, diff unchanged, empty diff

## Constraints

- Do NOT modify schema.py or db.py - both are already set up
- All new db access goes through existing db.py functions
- Use only stdlib: re, difflib, logging
- No new pip dependencies
- Do NOT reference ponytail, karpathy, opencode, AI agent, or any internal tooling names in any code, comments, or docstrings
- Follow existing code style (type hints, docstrings, logging patterns)

## Verification

1. All 3 new test files pass (pytest)
2. Existing tests still pass (test_crawler.py, test_db.py)
3. Pipeline runs without errors on existing data
4. Dashboard loads and shows filing details

After finishing, run grep for "ponytail|karpathy|opencode" on all changed .py files to verify no internal terms leaked.
