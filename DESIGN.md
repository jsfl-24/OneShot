# OneShot Design System

**Concept — "the camera report".** OneShot is the instrument that sits between the
script supervisor's camera report and the shot list. The interface borrows that
working document's language: slate-numbered scenes, timecode numerals, dense
lists of takes, and a single amber tally light for whatever is currently live.

This is a tool for filmmakers on a laptop in pre-production, not a marketing
page and not a generic SaaS dashboard. It should read as precise, quiet and
physical: flat surfaces, strong hierarchy, no ornament that does not carry
information.

---

## 1. Design tokens

All colour, spacing, type and motion decisions resolve to these tokens. A rule in
`styles.css` that hard-codes a value outside this table is a bug.

### Colour

| Token | Value | Role |
| --- | --- | --- |
| `--bg` | `#101116` | Application ground, input wells |
| `--panel` | `#191b21` | Cards, panels, dialogue surface |
| `--panel-raised` | `#23262e` | Selected rows, nested surfaces, hover fills |
| `--line` | `#2e313a` | Hairlines and borders |
| `--line-strong` | `#3a3e49` | Emphasis borders, inactive status dots |
| `--text` | `#e8e6df` | Primary ink (warm paper white) |
| `--muted` | `#8a8f98` | Secondary ink, metadata, disabled text |
| `--accent` | `#f2c94c` | Tally light — live, active, attention only |
| `--accent-ink` | `#1d1a0f` | Text on amber fills |
| `--ok` | `#8bd39a` | Approved / success |
| `--danger` | `#f2756a` | Destructive / error |

**Accent discipline.** Amber is a state, never decoration:

| Allowed | Not allowed |
| --- | --- |
| Active stage underline, active tab label | Card borders by default |
| Running task card, progress bar | Section headings, icons, tags |
| Current edit mode, focus ring | Primary buttons outside the one main action |
| Attention/selection markers (scene number chips) | Hover blobs or glows |

Green and red are semantic only. A shot card turns green only when approved; red
appears only on destructive actions and errors.

### Spacing and shape

| Token | Value |
| --- | --- |
| `--space-1` … `--space-6` | `4px`, `8px`, `12px`, `16px`, `24px`, `32px` |
| `--radius-sm` | `4px` (small controls, chips) |
| `--radius-md` | `8px` (buttons, inputs, cards) |
| `--radius-lg` | `12px` (dialogs, large panels) |
| `--bar-h` | `56px` (application bar) |
| `--rail-h` | `44px` (stage rail) |
| `--gutter` | `28px` desktop, `20px` tablet, `16px` phone |
| `--canvas-max` | `1440px` |

Surfaces separate by **tone step**, never by shadow. Hairlines are reserved for
dense data rows and input boundaries. Shadows are reserved for floating layers:
activity drawer, dialogs, tooltips.

### Type

| Token | Value |
| --- | --- |
| `--font-sans` | `system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` |
| `--font-mono` | `ui-monospace, SFMono-Regular, Consolas, monospace` |

No webfonts. The app must render offline and load with zero external requests.

| Role | Spec |
| --- | --- |
| Body | 15px / 1.55, `--text` |
| Stage title | 23px, weight 720, letter-spacing −0.02em |
| Section title | 14px, weight 700 |
| Label / kicker | 11px, uppercase, letter-spacing 0.12em, `--muted` |
| Metadata | 12–13px, `--muted` |
| **Data numerals** | `--font-mono`, 10–12px, `font-variant-numeric: tabular-nums` |

Data numerals are the signature: scene numbers, stage indices, shot references,
durations, counts and timecodes are always set in the mono stack with tabular
figures. Prose is always sans. Do not set sentences in mono and do not set
numbers in sans.

---

## 2. Layout

```
┌──────────────────────────────────────────────────────────────┐
│ OneShot  PRE-PRODUCTION   Project … Script …   ●health ⚙ ▤   │  app bar 56px
├──────────────────────────────────────────────────────────────┤
│ 01 Script  02 Scenes  03 Constraints  04 Shots  05 Storyboard│  stage rail 44px
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                    stage canvas (≤1440)                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                                        activity drawer 360px →
```

- **App bar** is persistent and sticky: brand, current project/script context,
  provider health, settings, activity toggle.
- **Stage rail** is the only primary navigation. Five stages in pipeline order;
  Storyboard stays visible and marked locked until Phase 7.
- **Stage canvas** is one content column per stage, capped at 1440px. Script is
  narrower (~820px) because it is a form, not a board.
- **Activity drawer** is an overlay, not a column. It preserves the ~25% width
  the old permanent console consumed and is opened deliberately (or by a run in
  later milestones).

### Stage rules

| Stage | Purpose | Width |
| --- | --- | --- |
| Script | Create project, upload screenplay, screenplay metadata | narrow |
| Scenes | Run detection/analysis; review the one canonical scene list | full |
| Constraints | Project defaults + scene overrides | full, two columns from M4 |
| Shots | Primary workspace: generate, edit, reorder, approve | full |
| Storyboard | Locked expectation for Phase 7 | narrow |

Stages are never trapped: any stage with data can be entered directly. Forward
CTAs chain the happy path; backward navigation never discards state.

---

## 3. Components

### App bar
56px, sticky, `--bg` at 97% opacity with a hairline. Brand uses the sans stack
at 17px/750; the "PRE-PRODUCTION" kicker uses the label role. The context line
shows project and script names, truncated with ellipsis. Actions are ghost
buttons; the activity toggle carries a count badge when the log is non-empty.

### Stage rail
44px, sticky under the app bar. Each stage is a button with a mono index
(`01`…`05`), a name, and a 6px readiness dot. Active stage: `--text` label, amber
2px underline, amber index. Locked Storyboard: 60% opacity, lock glyph, still
navigable to its locked panel.

Dot states: empty = not started, muted = stage has data, green = stage complete
(script selected, scenes analysed, approved shots present). Constraints has no
reliable completion signal, so it shows muted once scenes exist.

### Buttons
- `.btn.primary` — amber fill, dark ink. One primary action per screen region.
- `.btn.ghost` — transparent, hairline border, `--text`; hover border/text amber.
- Small row actions use the ghost style at 12px with 5×10px padding.
- Disabled buttons are not hidden; they carry `data-tip`/`title` with the reason.

### Inputs
Dark wells (`--bg` on panels, `--panel-raised` in the app bar strip), 1px
`--line`, 8px radius, 8×10px padding. Labels use the label role. Focus is the
single amber 2px ring with 2px offset.

### Data cards
Scene, shot and constraint cards share one shape: `--panel` fill, 1px
`--line`, 9px radius, no shadow. Summaries are flex rows; dense data sections
use 1px separators. Selected/active cards step up to `--panel-raised` and gain
an amber left border only when selection is meaningful.

### Empty, loading, success, error
- Empty: dashed 1px `--line`, `--panel` at 45%, title + detail + one CTA.
- Loading: text states in the same container ("Reading scenes…", "Loading
  shots…"); the activity task card carries the amber progress bar.
- Success: green text in the activity log and green approved tags; no toast
  layer.
- Error: red banner above the stage (role="alert"), red activity entry, and the
  same message in `title`/`data-tip` of the disabled action that caused it.

### Activity drawer
360px overlay, full height, `--panel` surface, left hairline, one shadow.
Header has "Activity" + live indicator + Close. Task card sits above a scrolling
log. Entries: mono timestamp, colour-coded left rule (green ok, red error,
muted info). Closes on Close, scrim click and Escape; focus returns to the
toggle.

### Dialogs
Native `<dialog>` with a 12px radius, `--panel` surface, 1px border and the
existing dark scrim. Destructive confirmation uses `window.confirm` until a
dedicated confirm component is justified.

---

## 4. States and interaction

- **Motion** is functional only: 150–200ms ease-out on state changes, drawer
  slide, progress. No entrance choreography. `prefers-reduced-motion: reduce`
  collapses all animation to 0.01ms.
- **Focus** is always visible. Stage rail supports Left/Right/Home/End.
- **Hash routing** (`#/script` … `#/storyboard`) makes back/forward and refresh
  preserve the stage. In-memory selection and per-stage caches are never reset
  by navigation.
- **Destructive actions** require confirmation and name the object.
- **No dead ends**: every empty state offers the next action.

---

## 5. Responsive behaviour

| Width | Behaviour |
| --- | --- |
| ≥1280 | Full canvas, 28px gutters, context visible in app bar |
| 1100–1279 | Full canvas, 20px gutters, context truncates |
| 760–1099 | App context hidden; health chip compact; drawer still overlays |
| <760 | 16px gutters, brand kicker hidden, settings label hidden, stage rail scrolls horizontally, buttons may go full width |
| 390 | Usable single column; health chip shows dot + short status only |

The primary target is a laptop on set. Mobile is supported, not designed
separately.

---

## 6. Accessibility and quality bar

- Landmarks: `header`, `nav`, `main`, `aside`, `dialog`; tablist/tab/tabpanel
  semantics on the stage rail.
- All icon-only controls have `aria-label`; status changes use `aria-live`
  where the text is the only signal.
- Contrast: body text ≥ 7:1 on `--bg`; `--muted` ≥ 4.5:1 on `--panel`.
- No external network requests from `/ui` (no CDN fonts or styles).
- No colour-only meaning: status dots carry labels/context, errors carry text.

---

## 7. Implementation status

| Milestone | Scope | State |
| --- | --- | --- |
| M1 | Tokens, app bar, stage rail, hash routing, activity drawer, views re-homed | implemented |
| M2 | Script stage + header project/script switchers | pending |
| M3 | Scenes stage: pipeline header, scene timeline, analysis states | pending |
| M4 | Constraints stage + dialog restyle | pending |
| M5 | Shots stage — Phase 5 behaviour ported and slate-styled | pending |
| M6 | Storyboard lock polish, responsive, keyboard/guidelines pass, final QA | pending |

Anything not listed as implemented above is not claimed to exist.
