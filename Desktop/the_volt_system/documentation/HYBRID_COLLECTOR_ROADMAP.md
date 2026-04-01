# Hybrid Collector Roadmap

## Core Principle

All collectors must return a pandas DataFrame through one uniform interface.
The pipeline should not depend on collection method details.

Minimum required columns for every collector output:

- `timestamp`
- `source`
- `fetched_at_utc`

Collectors may add any extra fields (`symbol`, `value`, `title`, `link`, etc.), but must preserve the minimum contract above.

## Build Order (Execution Plan)

### Phase 1: BrowserCollector (Playwright)

Targets:

- TradingView
- Investing.com

Why first:

- Highest value data gap.
- Often inaccessible via clean public APIs.
- Browser automation still yields structured extraction without desktop fragility.

Deliverables:

- `data_api/collectors/browser_collector.py`
- Settings for browser targets and run flags.
- Raw file outputs under standard FileStore naming (`browser_*`).
- DataFrame contract validation before save.

Acceptance criteria:

- Both targets produce non-empty DataFrames with required columns.
- Pipeline can run with browser collection enabled or disabled.
- Retries/timeouts and per-target error isolation are implemented.

### Phase 2: RedditCollector + MacroCollector (API-native)

Targets:

- Reddit (PRAW)
- FRED macro indicators

Why second:

- Fastest to implement and maintain.
- Adds high-value orthogonal signals (social + macro) currently absent.

Deliverables:

- `data_api/collectors/reddit_collector.py`
- `data_api/collectors/macro_collector.py`
- Settings for subreddit/topic queries and FRED series list.
- Pipeline merge hooks for new collectors.

Acceptance criteria:

- Reddit and FRED collectors return contract-compliant DataFrames.
- New sources are persisted and traceable by `source` value.
- Training export can include derived features from these feeds.

### Phase 3: DesktopCollector (PyAutoGUI + mss)

Why last:

- Most fragile layer due to OS/screen layout dependency.
- Best reserved for sources with no viable API/browser path.

Deliverables:

- `data_api/collectors/desktop_collector.py`
- Optional desktop target config.
- Guard rails: fail-safe, bounded retries, and non-blocking behavior.

Acceptance criteria:

- Desktop collection does not break pipeline when unavailable.
- Captures are auditable and mapped to source metadata.

## Vision-Extraction Layer (On Top of Desktop)

Design:

- Capture screenshot frames.
- Pass image to vision extraction model with natural-language schema instructions.
- Convert extracted JSON to DataFrame and enforce collector contract.

Why this matters:

- Reduces dependence on brittle pixel coordinates/selectors.
- More resilient to layout changes and UI redesigns.

## Router Rule

A future `CollectorRouter` should choose layer per source:

- Public documented API exists -> API collector.
- Auth-only/dynamic web content -> Browser collector.
- Desktop-only data source -> Desktop collector (+ vision extraction).

The pipeline must always receive the same DataFrame contract regardless of route.

## Suggested File Changes

New files:

- `data_api/collectors/browser_collector.py`
- `data_api/collectors/reddit_collector.py`
- `data_api/collectors/macro_collector.py`
- `data_api/collectors/desktop_collector.py`

Updates:

- `data_api/config/settings.py` (target lists + feature flags)
- `data_api/jobs/pipeline.py` (invoke and persist additional collectors)
- `data_api/app.py` (optional endpoints for new collector families)

## Non-Negotiable Engineering Rules

- Every collector returns a DataFrame with `timestamp`, `source`, `fetched_at_utc`.
- Never allow one collector failure to abort the whole run.
- Preserve source provenance in all intermediate and exported datasets.
- Keep notebook experimentation separate from production entrypoints.
