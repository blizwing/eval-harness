# CLAUDE.md

Project context for Claude Code sessions in this repo.

## What this is
An LLM evaluation harness for scoring LLM-generated test cases against a
labeled dataset, using deterministic assertions and an LLM-as-judge. Phase 1
of a three-project, six-month plan (see README.md).

- **P1 — Eval Harness** (this repo): proves AI Quality / Evaluation. 11 Aug – 13 Sep 2026.
- **P2 — Ambiguity Chaser** (LangGraph agent, separate repo): proves agentic dev + GenAI. Sep–Nov 2026.
- **P3 — Agent Eval Layer** (fine-tuned classifier): proves QA for non-deterministic systems. Dec–Jan.

Repo: `blizwing/eval-harness` (public). Structure is flat at root except
per-day artifact folders.

## Where things live
- `NOTES.md` — daily build log, one dated entry per roadmap day.
- `BACKLOG.md` — deferred ideas that were deliberately not built yet, each
  with a stated revisit trigger. Check this before proposing new components
  or features, so we don't rebuild something already considered and parked.
- `schemas.py` (added Day 24) — all Pydantic models consolidated here:
  `Requirement`/`RequirementSet` (Day 22), `TestCase` (Day 7), `JudgeVerdict`
  (Day 12), `CaseResult` (Day 23, promoted from dataclass to BaseModel),
  `ScoreResult`/`JudgeScore` (Day 24), `PassRates`/`CostReport`/
  `LatencyReport`/`AssertionFailure`/`JudgeFailure`/`FailureReport`/`Report`
  (Day 25).
- Per-day data artifacts live in `DayN_Description/` subfolders; code files
  are flat at repo root.
- **Critical filename:** the requirements dataset is at
  `Day8_Project_Requirements/fsm_requirements.yaml` — not `requirements.yaml`.
  Always use the full path.
- Env vars for API base URLs: `DEEPSEEK_OPENAI_BASE_URL`,
  `DEEPSEEK_ANTHROPIC_BASE_URL`, with hardcoded strings as defaults (Day 23).

## Resolved: grader-output integrity (flagged 1 Sep 2026, closed Day 24)
External feedback (via LinkedIn, from an AI engineer working on memory/eval
systems) flagged that the harness needs to assert on its own grader output,
not just the model's output — they'd seen a real case with 8 eval fields at
0/5797 populated, zero errors raised, dashboard reporting fake coverage.

**Closed in Day 24** via `ScoreIntegrityError`: every `ScoreResult` is
checked for presence, correct key sets, and non-blank reasoning before being
returned. Failure hard-halts `score_all()` rather than degrading to a
per-row status (that's how `api_error` rows are handled instead — a
different, lower severity). This also directly connects to the Day 18
"borderline path structurally unreachable" finding — that dead path was a
live instance of exactly the failure mode raised in that feedback. Good
combined interview anecdote.

Leave this section in as historical record — don't re-open unless the
integrity check itself is found to have a gap.

## Key findings that shape design decisions
- **Non-determinism (Day 2):** temp=0 is not fully deterministic, and it
  differs by API surface — OpenAI-schema endpoint was fully deterministic at
  temp=0, Anthropic-schema endpoint was not (5/10 unique outputs against the
  same model). **Implication: eval regression checks cannot use exact-match;
  use pass-rate thresholds over multiple runs instead.** This is the
  founding premise of Day 26 (regression baseline/diffing).
- **JSON mode fabrication (Day 4):** the model returns plausible-looking
  values for fields it can't actually know, with no refusal, no null, no
  malformed JSON — indistinguishable from grounded output unless you already
  know the field is ungroundable.
- **Priority field failure (Day 7):** every valid TestCase response returns
  `priority='high'` regardless of requirement content — the zero-shot prompt
  gives no grounding criteria for priority selection. Week 3 follow-up
  planned: add explicit grounding (tie priority to stated user/business
  impact) and rerun, checking both drop-rate and whether values stop being
  uniformly 'high'.
- **Judge vs. human agreement (Days 14–19):** v1 rubric 90% (9/10) agreement;
  v2 named-criteria rubric regressed to 80% (8/10) on the 10-item set —
  documented as an honest small-n result, not overclaimed. On the expanded
  35-item set: 71.4% agreement, precision 60%, recall-strict 60%,
  recall-inclusive 27.3%.
- **Borderline path (Day 18 → Day 24, evolving finding):** Day 18 found the
  judge's "borderline" verdict was never emitted across all 35 real rows —
  looked structurally unreachable. Day 24 built 5 targeted borderline
  requirements to test this directly: still never landed on borderline under
  the harness's default model (`deepseek-v4-flash`, no thinking) across 2
  runs — sharpened conclusion to "judge behaves as a near-binary classifier."
  **But** a follow-up model-variant experiment (same 5 requirements under
  flash+thinking, pro, pro+thinking) reached borderline once, under
  pro+thinking, on `req_b04`. **Revised conclusion: borderline is not
  structurally unreachable — the default model/setting just isn't
  discriminating enough to reach it.** Do not change the default pipeline
  model on the strength of this one data point; see BACKLOG.md item on a
  proper judge-model comparison first.
- **Contradictory requirements are out of scope for Phase 1** (Day 17): the
  per-requirement design can't catch contradictions, since that requires
  holding two requirements in view simultaneously. This is explicitly P2
  territory (Ambiguity Chaser), not a Phase 1 gap to fix.
- **Error status design principle:** unify error statuses around caller
  behavior, not failure-cause granularity. `"invalid_schema"` intentionally
  covers multiple distinct failure modes because the caller's response is
  identical in every case. Don't split statuses just because the underlying
  causes differ, if the handling doesn't.
- **Temperature must be explicit (Day 23):** a silent default of
  `temperature=1.0` inside `LLMClient` was a real bug that could silently
  corrupt reproducibility. Fixed via a named `TEMPERATURE` constant. Always
  pass temperature explicitly, never rely on a provider default.

## Known bugs fixed (context for why code looks the way it does)
- **`Day11_assertions.check_valid_json` crash bug (found/fixed Day 24):** it
  scanned `validation_detail` for a `"json_error"`-tagged tuple to detect
  parse failures, but `Day5_validate.validate_response` never actually
  emitted that tag — its `invalid_json` status carries a bare list of
  exception-message strings. The old code coincidentally always returned the
  right answer for 24 days (the tag never matched, so it always fell through
  to `True`) until a genuine `invalid_json` row occurred for the first time
  (`req_b01`, under flash+thinking), which crashed the unpack. Fixed to
  check `validation_verdict != "invalid_json"` directly.
- **Row-key mismatch (found/fixed Day 24):** Day 11's assertion checks read
  `row["validation_verdict"]`; Day 23's runner rows use `row["status"]` for
  the same concept. Fixed with a row adapter inside `Day24_scorer.py` rather
  than touching Day 11's checks.
- **`JudgeScore` field mismatch (found/fixed Day 24):** originally specced
  with 3 fields to match judge v1, but the harness's default prompt is
  `judge_v2.txt`, whose rubric needs 5. Validating a v2 response against the
  3-field model would have silently dropped `verification_fidelity` and
  `pass_fail_clarity` from every score with no error — the same silent-wrong-
  answer failure mode raised earlier, but in the schema layer. `JudgeScore`
  expanded to all 5 fields.
- **`day5_validate.py` filename case bug (open, Day 5):** file is tracked on
  GitHub as `day5_validate.py` (lowercase d) but imported as
  `Day5_validate` (capital D) in places. Works on Windows (case-insensitive
  filesystem), breaks on Linux/CI. Not yet fixed — flag if it surfaces in a
  CI context.

## Roadmap status (as of 5 Sep 2026)
Complete through **Day 25**. Day 26 (Sat 5 Sep, "home turf," no session) is
next: regression baseline/diffing.

- Save results to `baseline.json`.
- Diff subsequent runs against it, flag regressions.
- Core design problem: outputs are non-deterministic (Day 2), so this must
  use pass-rate thresholds, not exact-match diffing.
- **DONE WHEN:** deliberately worsening the prompt makes the tool report a
  regression.
- The prompt to deliberately worsen for this test is `prompt_testcase_v1.txt`
  (Day 7) — the zero-shot prompt that drives test-case generation, i.e. the
  thing the whole harness measures the quality of. Use a second/sabotaged
  copy, don't overwrite the real file.

Real numbers from the current 35-case dataset (Day 25 report), useful as
the baseline reference point: assertion pass rate 97.1% (34/35), judge pass
rate 94.3% strict-good (33/35), total cost $0.0050, mean latency ~2989ms.

### Upcoming after Day 26
- **Day 28:** use the harness on the Day 7 prompt itself — improve it based
  only on what the tool reports, re-run, get before/after numbers.
- **Days 29–33 (Week 5):** CI via GitHub Actions, pass-rate gate that fails
  CI on regression, cost guardrail with hard abort, tests for the harness
  itself (mocked API, no network in `pytest`), final README with Day 19
  metrics table and 400–600 words on the Day 14 judge-disagreement finding.
- **Day 34 (Sun 13 Sep): ship.** Public repo, README complete, CI green,
  message the two senior advisors separately (not copy-pasted) — what was
  built, one surprise, no ask. Then start `ambiguity-chaser` repo (P2).

### BACKLOG.md items to know about
- Typo/grammar checking via a cheaper model.
- ~~Grader-output integrity check~~ — **closed Day 24**, see section above.
- Pre-generation quality gate — deferred to P2 (Ambiguity Chaser).
- Proper judge-model comparison (flash vs flash+thinking vs pro vs
  pro+thinking) before changing the default pipeline model — added Day 24
  off the borderline-path model-variant experiment.

## Workflow conventions (how Pratham and Claude work together on this repo)
- **All actual repo work happens on Pratham's machine.** Claude gives code,
  file content, or Claude Code prompts for Pratham to run — Claude does not
  create, edit, or execute project work in its own sandbox. Exception:
  read-only verification (cloning/fetching to confirm a commit landed or a
  file exists) is fine and encouraged.
- **Daily workflow:** (1) verify prior day's work is actually present before
  starting a new day; (2) state that day's objective and DONE WHEN from
  roadmap.md, flag upfront whether it's a "Pratham writes first draft"
  (new concept/judgment call) or "Claude writes first draft, Pratham
  reviews/runs" (repetitive plumbing) day, get agreement before starting;
  (3) build/guide accordingly; (4) after DONE WHEN is confirmed, run an
  end-of-day understanding check on the WHY behind decisions, not the WHAT —
  no trivially guessable questions.
- **NOTES.md authorship (Day 25+):** Claude drafts the day's NOTES.md entry;
  Pratham reviews, edits, and validates before committing. This does not
  change the sandbox restriction above — Claude still never commits.
- **Claude Code prompts should:** include explicit pre-flight checks
  (confirm the target script exists, report non-valid counts); never touch
  `NOTES.md`/`BACKLOG.md` autonomously; never commit — Pratham reviews the
  diff and commits himself, since that's how changes sync across his two
  computers.
- **Code ownership split:** Pratham writes domain judgment, requirement
  wording, labeling, and first-draft code on judgment-heavy days. Claude
  scaffolds plumbing, wrappers, and repetitive structure. Claude flags
  inconsistencies; Pratham makes the calls.
- **GitHub verification pattern:** `curl` against
  `raw.githubusercontent.com/{user}/{repo}/{branch}/{path}` for live file
  content — avoid `api.github.com` (60 req/hr unauthenticated limit). To
  confirm commits landed, `rm -rf` a cached clone and re-clone with
  `git clone --depth 1` rather than relying on `git pull`. Avoid `web_fetch`
  on `github.com` URLs in long conversations — it can return stale cached
  data.
  