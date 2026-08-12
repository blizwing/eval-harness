# Notes

## Day 2 — Temperature and non-determinism (12 Aug 2026)

**Setup:** Same prompt ("Write a haiku about testing."), same model
(`deepseek-v4-flash`), 10 runs each at `temperature=0` and `temperature=1`,
across both the Anthropic-schema and OpenAI-schema endpoints.

**Finding: `temperature=0` does not guarantee determinism — and the degree
of non-determinism differs by API surface, not just by temperature.**

| Schema    | temp=0 unique outputs | temp=1 unique outputs |
|-----------|------------------------|-------------------------|
| OpenAI    | 1 / 10                 | 10 / 10                 |
| Anthropic | 5 / 10                 | 10 / 10                 |

### temp=0, OpenAI schema — fully deterministic
All 10 runs byte-identical:
> Assertions align, / Red builds fail, then green appears— / Truth in every run.

### temp=0, Anthropic schema — deterministic-ish, but leaky
6 of 10 runs matched that exact same OpenAI output. The other 4 drifted to
near-neighbor variants — same opening line every time ("Assertions align,"),
divergence confined to lines 2–3:
- "Red bar breaks the quiet calm—"
- "Red bar bleeds across the screen—"
- "Red failures light the dark path—"
- "Red bar bleeds into the dawn—"

The drift isn't random across the whole haiku — it's the model landing in
the same high-probability basin most of the time, occasionally slipping to
a nearby token at one specific branch point (after line 1).

### temp=1, both schemas — fully open
10/10 unique in both. Structurally different haikus each run; some drift
entirely off the testing metaphor (e.g. one output moved to a
medical/blood-vial image, another to a pregnancy/blooming image).

### Why this matters going forward
For the eval harness (Week 4+), "regression" against a baseline can't mean
exact-match on non-deterministic output — confirmed directly by this data,
not just by the general "temp 0 ≠ deterministic" claim from the LEARN step.
Pass-rate thresholds over multiple runs, not single-run diffing, are the
right approach. Also worth remembering later: if comparing providers or API
surfaces for consistency, the surface itself is a variable, not just the
model/temperature settings.

**Raw data:** `temp0_runs_anthropic.txt`, `temp0_runs_openai.txt`,
`temp1_runs_anthropic.txt`, `temp1_runs_openai.txt`