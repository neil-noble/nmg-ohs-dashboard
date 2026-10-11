# NMG OHS Dashboard — Design

Date: 2026-10-11
Status: design approved in conversation by Neil Noble; awaiting review of this written spec.

## 1. Purpose

A visual health and safety statistics dashboard for New Murchison Gold (NMG),
published at `https://www.emergencyservicesaustralia.com.au/nmg-ohs`.

It replaces a hand-kept Excel report (Mining / Exploration event table plus
TRIFR and LTIFR trend charts). Every figure is calculated from PeopleTray, so
the dashboard cannot drift from the system of record the way the spreadsheet
did (its "September" column held mostly August figures).

Success: on any day, the page shows the last completed month and financial
year to date for Mining and Exploration, in NMG branding, without anyone
keying numbers.

## 2. Architecture

Same publish pattern as NMG Fuel and NMG ERT.

| Piece | Location |
|---|---|
| Local project | `C:\claude\NMG OHS Dashboard` |
| Source repo (private) | `neil-noble/nmg-ohs-dashboard` |
| Published site repo (public, GitHub Pages) | `neil-noble/nmg-ohs-site` |
| Pages URL | `https://neil-noble.github.io/nmg-ohs-site/` |
| Wix page | `/nmg-ohs`, embedding the Pages URL in an iframe |

Flow:

1. GitHub Actions workflow `dashboard.yml` runs daily (and on manual dispatch).
2. `fetch.py` pulls PeopleTray into plain Python structures.
3. `metrics.py` turns those into one `report` dict (pure functions, no I/O).
4. `render.py` turns the `report` into a single self-contained `docs/index.html`
   (inline CSS, inline SVG charts, no JavaScript dependencies, no external
   requests apart from an optional web font).
5. The workflow pushes `index.html` to `nmg-ohs-site` using a `PAGES_TOKEN`
   secret. GitHub Pages serves it. Wix embeds it.

Python standard library only for fetch, metrics and render. `pytest` for tests.

Rejected alternatives: browser-side calls to PeopleTray (would expose the API
key); Streamlit (retired on the other NMG projects).

### Modules

| File | Responsibility | Depends on |
|---|---|---|
| `config.py` | Workgroup buckets, event-row mapping, injury classes, colours, financial-year start | nothing |
| `peopletray.py` | HTTP GET with `X-API-Key`, 4 retries with backoff | key from `PT_API_KEY` env, else local key file |
| `fetch.py` | Calls the five endpoints for the needed date window, returns raw lists | `peopletray.py` |
| `metrics.py` | Bucketing, classification, monthly counts, FYTD, rolling rates, head count, lost workdays, injury and action summaries | `config.py` |
| `render.py` | HTML and SVG from the `report` dict | `config.py` |
| `generate_dashboard.py` | Entry point: fetch, compute, render, write `docs/index.html` | all of the above |

### Secrets

- `PT_API_KEY` — GitHub secret on the source repo. Locally the key is read from
  line 2 of `C:\claude\PeopleTray DAS\reference\PT API Key for NMG.txt`. It is
  never copied into this repo.
- `PAGES_TOKEN` — PAT with contents:write on `nmg-ohs-site`.

## 3. Data sources (PeopleTray, base `https://api-peopletray.azurewebsites.net`)

| Endpoint | Used for |
|---|---|
| `/api/v2/powerbi/events?fromDate&toDate` | Event counts by type, workgroup, month; open vs closed |
| `/api/v2/powerbi/eventinjurylist?fromDate&toDate` | Injury class fallback, body location, nature, mechanism, return-to-work date |
| `/api/v2/powerbi/exposurehours?fromDate&toDate` | Person hours by workgroup and month |
| `/api/v2/powerbi/actions?fromDate&toDate` | Corrective actions: open, overdue, closed |
| `/api/v2/powerbi/people` | NMG head count |

Fetch window: from 23 months before the reporting month through to today
(the 12-month trend needs a rolling 12 months behind each of its 12 points).
Verified 2026-10-11: exposure hours exist from July 2025, events from June 2025.
A rolling window that reaches back before July 2025 uses the hours and events
that exist inside it. A window with no hours at all renders "NA", not zero.

Known data traps:

- `events.eventDate` is `dd-mm-yyyy`; use `eventDateTime` (ISO) for dating.
- `injuryType` values carry a trailing space, e.g. `"FAI (First Aid Injury) "`.
- Do not use `/api/v2/reporting/people/...` (pagination never terminates).

## 4. Calculation rules

### 4.1 Periods

- Reporting month: the last completed calendar month, by Australia/Perth time.
  On 2026-10-11 that is September 2026. It rolls on the 1st of each month.
- FYTD: 1 July of the financial year containing the reporting month, through
  the end of the reporting month.
- Rolling 12 months: the reporting month and the 11 before it.

### 4.2 Mining / Exploration buckets (by workgroup)

| Bucket | Workgroups |
|---|---|
| Mining | every workgroup starting `CPO - `; `Contractors - Local`; `Contractors - Other` |
| Exploration | every workgroup starting `GG - `; `Drilling Contractors` |
| Excluded | `Flight/Accommodation ONLY`; every workgroup starting `PER - ` |

A workgroup matching none of these is excluded from the figures and named in
an amber "Unmapped workgroup" notice on the page and in the workflow log, so a
new workgroup cannot silently lose events or hours.

The same buckets apply to events, hours and head count.

### 4.3 Injury classification

For events whose type is `Injury`:

1. Use `injuryType` when set (from `events`, else from the matching
   `eventinjurylist` row by `eventId`).
2. Otherwise use `eventSubType`.

| Class | From `injuryType` | From `eventSubType` |
|---|---|---|
| Lost Time Injury | `LTI…` | `Lost Time Injury` |
| Restricted Work Injury | `RWI…` | `Restricted Work Injury` |
| Medically Treated Injury | `MTI…` | `Medical Treatment Injury` |
| First Aid Injury | `FAI…` | `First Aid Injury` |
| No Treatment Injury | `NT…` | `No Treatment Required` |
| Not counted | `NWR…`, `PEC…` | — |

Total Injuries = the five counted classes. An injury event that maps to no
class is counted under an "Unclassified injury" row and flagged in the log.

### 4.4 Frequency rates

- TRIFR = (LTI + RWI + MTI) × 1,000,000 ÷ person hours, rolling 12 months.
- LTIFR = LTI × 1,000,000 ÷ person hours, rolling 12 months.
- In the event table the month column shows "NA" and the FYTD column shows the
  rolling 12-month rate, matching the existing report. A footnote says so.
- Zero hours in the window gives "NA".
- Rates are shown to two decimal places.

### 4.5 Event table rows

| Row | Source |
|---|---|
| Lost Time / Restricted Work / Medically Treated / First Aid / No Treatment Injury | 4.3 |
| Total Injuries | sum of the above |
| Near Miss | event type `Near Miss` |
| Lost Workdays | 4.7 |
| LTIFR, TRIFR | 4.4 |
| Environmental Incidents | event type containing `Environment` (none in use today; shows "–") |
| Production Loss | `Production Loss` |
| Procedural Compliance | `Procedural Compliance` |
| Property Damage / Loss | `Property Damage / Loss` |
| Security Incident / Violence | `Violence` + `Security` |
| Business / Operational Interruption | `Business / Operational Interruption` |
| Misfire | `Misfire` |
| Community / Heritage | `Community / Heritage` |
| NMG Head Count | 4.6 (month column only; FYTD "NA") |
| Total Person Hours Worked | exposure hours |

`Non Work Related` events are not shown. Any other event type not listed gets
its own row automatically. Zero is displayed as "–".

### 4.6 NMG head count

People with `employer == "New Murchison Gold Ltd"` and `emplpyeeType !=
"Contractor"`, bucketed by workgroup per 4.2 (Perth excluded), who were
employed on the last day of the reporting month: `dateCommenced` on or before
that day and `dateCeased` empty or after it. On 2026-10-11 the current-day
equivalent is Mining 22, Exploration 16.

Limitation: PeopleTray returns each person's current workgroup, not their
workgroup at month end.

### 4.7 Lost workdays

For each Lost Time Injury: calendar days from the injury date to
`returnWorkDate`, attributed to the month of the injury. An LTI with no return
date shows the row as "open" with a footnote, rather than a guessed number.

## 5. Page layout

Styling from the NMG stylesheet: Navy `#083045`, River `#55848A`, Gold
`#927128`, Pale Gold `#B19045`, Sand `#F1DCAA`, Cool Grey `#DBDBD3`, Black 93%
`#333334`, and their 50% tints. Font stack: Proxima Nova, Aptos, system sans.
Series colours: Mining = Navy, Exploration = Gold. Responsive down to phone
width so it works inside the Wix iframe.

Sections, top to bottom:

1. **Header** — NMG logo, "Health & Safety Performance", reporting month,
   "data as at" timestamp (AWST).
2. **KPI tiles** — for Mining and for Exploration: TRIFR, LTIFR, total
   injuries (month), days since last LTI, person hours (month).
3. **Event table** — rows per 4.5; columns Mining month, Mining FYTD,
   Exploration month, Exploration FYTD.
4. **TRIFR and LTIFR trend** — two line charts, 12 monthly points each, one
   line per bucket, month labels (e.g. "Oct 25"), with the definition footnote
   from the existing report.
5. **Event trend by type** — stacked monthly bars, last 12 months, both
   buckets combined, with a table view of the same numbers.
6. **Injury analysis** — horizontal bars for body location, nature and
   mechanism, rolling 12 months, counted injuries only. Records with the field
   blank are shown as "Not recorded".
7. **Open events and actions** — events open vs closed; actions open, overdue
   (open and past due date), and closed in the reporting month.
8. **Footer** — source (PeopleTray), definitions, bucket membership.

### Privacy

The Pages site is public. The page contains counts and rates only: no names,
no employee IDs, no event descriptions, no locations. A test asserts that no
person's name from the fetched data appears in the rendered HTML.

## 6. Error handling

- PeopleTray calls retry 4 times with backoff. If a fetch still fails, the
  workflow fails and the previously published page stays up. It never
  publishes a page built from partial data.
- A failed workflow emails Neil through GitHub's standard failure notification.
- Unmapped workgroups and unclassified injuries are visible on the page and in
  the log (4.2, 4.3).

## 7. Testing

`pytest`, run in the workflow before publishing. Fixtures are a saved,
de-identified PeopleTray sample.

- Bucket mapping, including an unmapped workgroup.
- Injury classification: `injuryType` wins over sub-type; blank falls back;
  NWR and PEC are not counted; trailing spaces tolerated.
- Period maths: reporting month roll-over on the 1st, FYTD across July,
  rolling 12 months.
- Rates: formula, zero-hours "NA", two-decimal rounding.
- Head count: employer and type filter, commenced / ceased boundaries.
- Lost workdays: with and without a return date.
- Render: every section present; September 2026 fixture reproduces the
  expected table; no names in the HTML.

Before going live, the rendered page is checked in a browser at desktop and
phone widths.

## 8. Project conventions

- `state.yaml` and a bootstrap-only `CLAUDE.md`, per Neil's state policy.
- `reference/peopletray_ohs.yaml` records the endpoint facts in section 3.
- `ruflo init` with the standard protective flags.
- `.gitignore` blocks key, token and secret files.

## 9. Out of scope for the first version

- Month picker or historical month views.
- Email distribution of the dashboard.
- Manual overrides of PeopleTray figures.
- Risk register, inspections and training data.

## 10. Steps that need Neil

- Creating the two GitHub repos and the `PAGES_TOKEN` (I can create the repos
  with `gh`; the PAT is created in the GitHub UI).
- Creating the Wix page `/nmg-ohs` with the iframe embed and publishing it.
  Each of these outward-facing steps is confirmed with Neil before it happens.
