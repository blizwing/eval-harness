---
name: ui-mockup-builder
description: >-
  Builds and revises static HTML/CSS mid-fidelity UI mockups for Phase 2b of a SoloShip
  project, in place of Penpot ΓÇö but only for a project whose own CLAUDE.md declares a
  "UI Design Override" opting out of the default Penpot-based /ui-design flow. This is a
  template installed by `soloship sync-skills`: self-gating, so if the current project's
  CLAUDE.md has no such override, it defers to the standard /ui-design (Penpot) command
  instead of taking over. Trigger whenever /ui-design or /ui-design-revise runs in an
  opted-in project, or the user asks in plain language to build, update, mock up, or
  wireframe a screen in such a project. Every field, screen, color, and copy string must
  trace back to that project's own 02-srs.md / 02b-ia.md, brand/resources/design-tokens.json,
  and brand/resources/voice-tone.md ΓÇö never invented, never borrowed from another project.
---

# UI Mockup Builder (HTML/CSS override) ΓÇö template

## Why this exists (read once)

SoloShip's default Phase 2b (`/ui-design`) drives Penpot canvas mockups. Some projects opt
out ΓÇö a personal project without Penpot set up, or an owner preference for plain static
HTML ΓÇö by declaring a "UI Design Override" section in their own project `CLAUDE.md`. Since
`.claude/commands/` is unconditionally overwritten by `soloship sync` / `sync-this`, a project
can't durably fork `ui-design.md` to hardcode that choice ΓÇö it has to be re-applied by
interpretation every run, or codified once as a project-scoped skill (`.claude/skills/` is
never touched by sync).

This file is the reusable **template** for that codification. `soloship sync-skills` installs
a copy into any project missing one, but never overwrites a project's own already-customized
copy ΓÇö e.g. `personal/card-scanner/.claude/skills/ui-mockup-builder/SKILL.md` has its actual
fields/screens/palette baked in directly and takes precedence there. Treat this generic
version as a starting point for a newly-opted-in project, not a control layer above a
project's own copy.

## Step 0 ΓÇö Self-gate (do this before anything else)

Read the current project's `CLAUDE.md`. Look for a section declaring that Phase 2b uses
static HTML/CSS instead of Penpot (card-scanner's is titled "UI Design Override" ΓÇö look for
that pattern or equivalent language).

- **No such override declared:** stop. Tell the user this project uses the standard
  `/ui-design` Penpot flow; either run that command, or add a "UI Design Override" section to
  this project's `CLAUDE.md` (see `personal/card-scanner/CLAUDE.md` for the pattern) if they
  want to opt this project into HTML mockups too, then re-invoke this skill.
- **Override declared:** continue with the workflow below. Once this project's own
  field/screen list stabilizes, consider replacing this generic file with a project-specific
  version (like card-scanner's) so future runs don't re-derive it from source docs every time.

## Source of truth ΓÇö read from the CURRENT project's own files, never another project's

| File | What it supplies |
|---|---|
| `02-srs.md` | Authoritative screen + field list (functional requirements) |
| `.project-config.yaml` | `platforms` map, `brand_status` gate |
| `brand/resources/design-tokens.json` | Typography scale, spacing scale, radii, color mode (fixed palette vs. dynamic) |
| `brand/resources/ui-constraints.md` | Touch targets, nav pattern, forbidden patterns per platform |
| `brand/resources/voice-tone.md` | Copy register, terminology, CTA vocabulary |
| `02b-ia.md` (if present) | Formal Phase 2a screen inventory ΓÇö authoritative over anything inferred from the SRS alone |
| an existing `brand/resources/palette-preview.html` (if present, for dynamic-color projects) | The already-established formula for illustrating dynamic color in a static mockup ΓÇö reuse it, don't invent a new one |

**Gate check:** if `brand_status` is not `approved`, stop and tell the user to complete
`/brand` ΓåÆ `/brand-revise` ΓåÆ `/brand-approve` first.

## Workflow

### Step 1 ΓÇö Derive the screen + field inventory
Prefer `02b-ia.md`'s screen inventory. If it doesn't exist yet, derive a fallback table
directly from `02-srs.md`'s functional requirements (and the brief's UI-flow section, if
any): one row per screen, listing fields shown / fields editable / actions available. Never
invent a field that isn't traceable to an FR.

### Step 2 ΓÇö File layout
`ui-mockups/` at the project root:
- `tokens.css` ΓÇö CSS custom properties generated from `design-tokens.json`
- `design-system.html` ΓÇö swatches / type scale / spacing scale reference (HTML equivalent of
  the root `/ui-design` command's Design System page)
- one self-contained `.html` file per screen/state row from Step 1, linking `tokens.css`

### Step 3 ΓÇö Color
Read `design-tokens.json`'s `colors.mode`:
- **Fixed palette:** use the listed hex values directly.
- **Dynamic (e.g. Material You / OS-derived color):** there is no locked palette to hand a
  static mockup. If the project already has a `palette-preview.html` (or similar) with an
  established illustrative-color formula, reuse it verbatim. If not, derive one following
  standard role-based 60/30/10 practice (dominant/secondary/accent, from the token file's
  documented role list), pick ONE consistent illustrative seed across all screens, and write
  it down (e.g. as a new `palette-preview.html`) so the next run doesn't re-derive it. Every
  dynamic-color mockup must carry a small visible caption stating the palette shown is
  illustrative, not locked.

### Step 4 ΓÇö Typography, spacing, radii
Pull directly from `design-tokens.json` ΓÇö no freehand pixel values, the same non-negotiable
rule the Penpot-based `/ui-design` command enforces via token application, enforced here via
CSS variables.

### Step 5 ΓÇö Device frame
Use the platform frame sizes from the root `/ui-design` command's own table:

| Platform | Primary | Secondary |
|---|---|---|
| `web` | 1440├ù900 | 390├ù844 |
| `mobile_ios` | 390├ù844 | 430├ù932 |
| `mobile_android` | 360├ù800 | 412├ù915 |
| `tablet` | 820├ù1180 | 1024├ù1366 |
| `desktop_app` | 1440├ù900 | 1920├ù1080 |

Build only for platforms marked `true` in `.project-config.yaml`'s `platforms` map.

### Step 6 ΓÇö Navigation pattern
Read `ui-constraints.md` for the project's own nav rules (tab bar, sidebar, none, etc. ΓÇö
per platform). Never default to a generic nav pattern; a small single-flow app may explicitly
forbid persistent nav.

### Step 7 ΓÇö Copy
Pull every label/button/message from `voice-tone.md` ΓÇö never lorem ipsum, never generic
marketing copy.

### Step 8 ΓÇö Constraint check before finalizing each screen
Re-read `ui-constraints.md`'s "Forbidden UI Patterns" section (if present) and confirm none
were violated; confirm state variants (loading/empty/error) called out in `02b-ia.md` or the
SRS are covered.

### Step 9 ΓÇö Write/update `02b-ui-designs.md`
Same structure the Penpot-based `/ui-design` command produces, translated: list
`ui-mockups/*.html` paths instead of a Penpot File ID, plus design decisions and open
questions.

### Step 10 ΓÇö Review loop
`/review 02b-ui-designs.md` for inline comments on the doc; there's no canvas, so visual
feedback comes back as plain-language notes applied via normal file edits under
`/ui-design-revise`.

## What NOT to do

- Don't run this workflow at all for a project that hasn't declared the override (Step 0) ΓÇö
  use the standard Penpot `/ui-design` command instead.
- Don't call any `mcp__penpot__*` tool from inside this skill.
- Don't copy another project's field list, palette, or copy strings ΓÇö every value must trace
  to THIS project's own SRS/IA/tokens/voice-tone files.
- Don't build screens for platforms not marked `true` in this project's own `platforms` map.
- Don't hand-pick pixel/spacing/radius values instead of the project's own token scale.
- Don't fork `.claude/commands/ui-design.md` or `ui-design-revise.md` to hardcode any of this
  ΓÇö `soloship sync`/`sync-this` silently overwrites that folder. `.claude/skills/` is the
  durable location.
