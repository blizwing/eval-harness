# 6-Month Roadmap — AI Engineering + AI Quality

**Day 0:** Monday 10 August 2026 — setup only
**Day 1:** Tuesday 11 August 2026 — official start
**Phase 1 ends:** Sunday 13 September 2026

---

## How to read a day

- **LEARN** — read/watch *before* touching code. Time-boxed. Over the box? Stop and build anyway.
- **BUILD** — what you write.
- **DONE WHEN** — the checkpoint. Can't tick it? The day isn't finished. Carry to the buffer day.

**Weekday:** 1.5 hrs → ~30 min learn, ~60 min build.
**Weekend:** 4 hrs.
**Every Sunday is a buffer day.** Catch up, or rest. Never add new work to Sundays.

## On `/advanced-learn`

The skill is a single-sitting immersion. It does **not** fit a 30-minute weekday slot — you'd get an orientation and two steps, then stall. So:

- **Saturdays = `/advanced-learn` sessions.** Seven of them across six months, on the topics that actually trap people.
- **Weekdays = doc reading.** "Read the Messages API page" doesn't need a crash course.
- Every prompt below is deliberately narrow and loaded with your background. Paste it as-is.

---

## The three projects

| # | Name | Proves | Dates |
|---|------|--------|-------|
| P1 | **Eval Harness** | AI Quality / Evaluation (Nagam) | 11 Aug – 13 Sep |
| P2 | **Ambiguity Chaser** | Agentic dev + GenAI (Tejsinh) | Sep – Nov |
| P3 | **Agent Eval Layer** | QA for non-deterministic systems (both) | Dec – Jan |

---

# DAY 0 — Monday 10 August (today)

**Setup only. ~1 hour. No learning.**

- [ ] Confirm compute. Weeks 1–14 need only a laptop. Week 18 needs the GPU. Flag the gap now, not in December.
- [ ] Python 3.11+ installed. Verify: `python --version`
- [ ] Public GitHub repo `eval-harness`, README with one line of intent
- [ ] `python -m venv .venv`, activate, add `.venv/` to `.gitignore`
- [ ] API key (Anthropic or OpenAI). **Set a hard spend cap. $10 covers Phase 1.**
- [ ] Key in `.env`. `.env` in `.gitignore`. Commit.

**DONE WHEN:** repo is on GitHub with one commit, and `.env` is *not* in it.

**✅ Completed 11 Aug 2026** — see `NOTES.md` Day 0.

---

# WEEK 1 — What an LLM call actually is
*11–17 August*

### Day 1 — Tue 11 Aug
**LEARN (30 min):** Your provider's "Messages API" doc page. Request/response structure only. Ignore streaming and tools.
**BUILD (60 min):** One file. Send "Write a haiku about testing." Print the *entire* response object. Then print separately: text, input tokens, output tokens, stop reason, model name.
**DONE WHEN:** you can point at all five values in your terminal.

**✅ Completed 11–12 Aug 2026** — see `NOTES.md` Day 1. Refactored into a shared
`CallResult` dataclass and one `report()` helper reused from Day 2 onward.

### Day 2 — Wed 12 Aug
**LEARN (20 min):** Search "LLM temperature explained." Key idea: temperature 0 ≠ deterministic.
**BUILD (70 min):** Same prompt ×10 at `temperature=0`, save to file. Repeat at `temperature=1`. Diff them manually.
**DONE WHEN:** you can state from your own data whether temp 0 gave identical output every time.

**✅ Completed 12 Aug 2026** — see `NOTES.md` Day 2. Temp=0 was fully deterministic
on the OpenAI-schema endpoint (10/10 identical) but only 6/10 identical on the
Anthropic-schema endpoint against the same model — the API surface itself affects
determinism, not just temperature.
*Most important observation of the six months. Non-determinism is why AI evaluation exists.*

### Day 3 — Thu 13 Aug
**LEARN (25 min):** Your provider's pricing page. Input vs output token cost differ — usually a lot.
**BUILD (65 min):** `llm_client.py` — wrapper returning text plus `{input_tokens, output_tokens, latency_ms, cost_usd}`. Print running total.
**DONE WHEN:** two calls print an accurate cumulative cost.

**✅ Completed 13 Aug 2026** — see `NOTES.md` Day 3. `LLMClient` in
`Day3_llm_client.py` wraps Day 1's call functions and tracks `total_cost_usd`,
`total_input_tokens`, `total_output_tokens`, `call_count` across calls. Pricing is
hardcoded from a point-in-time check — flagged to re-verify before relying on it
past the Phase 1 $10 cap.
*Keep this file. Used in every project for six months.*

### Day 4 — Fri 14 Aug
**LEARN (30 min):** Search "structured output JSON mode" for your provider.
**BUILD (60 min):** Request `{"summary": str, "risk_level": "low"|"medium"|"high"}` for a paragraph. Then break it — ask for a field it can't know. Log the failure shape.
**DONE WHEN:** you have one example your code couldn't parse or trust.

**✅ Completed 14 Aug 2026** — see `NOTES.md` Day 4. Two findings: an ungroundable
field (`estimated_fix_hours`) was fabricated cleanly with zero error signal, and
`risk_level` was inconsistent across repeated calls even at `temperature=0` on a
borderline paragraph. Both feed directly into Day 5's validator and the Week 4
scorer design.

### Day 5 — **Sat 15 Aug — `/advanced-learn` SESSION 1** (4 hrs)

```
/advanced-learn structured output and schema validation for LLM responses in Python

Context: I'm a QA automation engineer, 3 years, Java/Selenium primary, comfortable
with Python basics but new to LLM APIs. I've spent four days making raw API calls
and I've already seen the model return malformed JSON and invent fields it couldn't
know. Today I need to build a validation layer using Pydantic that fails loud and
distinguishes between three failure modes: invalid JSON, valid JSON with missing
fields, and valid JSON with wrong types. This feeds an eval harness I'm building.
Assume I know assertions and test design — I don't need testing concepts explained,
I need the LLM-specific traps.
```

**DONE WHEN:** three deliberately broken responses give three distinct readable errors.

**✅ Completed 15 Aug 2026** — see `NOTES.md` Day 5. Went past the bar: also
catches multiple simultaneous failures in one payload (missing field + wrong
type together) instead of only reporting the first one found.

### Day 6 — Sun 16 Aug — **BUFFER**

### Day 7 — Mon 17 Aug
**LEARN (30 min):** Search "few-shot prompting." Zero-shot vs few-shot.
**BUILD (60 min):** Prompt that turns a plain-English requirement into a structured JSON test case. Zero-shot. Store the prompt in its own file, not hardcoded.
**DONE WHEN:** one requirement in, parseable JSON out.

---

# WEEK 2 — Build something imperfect, then measure it
*18–24 August*

### Day 8 — Tue 18 Aug
**BUILD (90 min):** Write 10 requirements by hand from your FSM/HRMS work. **Anonymize** — no company, client, or internal system names. Store as `requirements.yaml`.
**DONE WHEN:** 10 exist, and you'd be fine with a stranger reading them.

### Day 9 — Wed 19 Aug
**BUILD (90 min):** Run Day 7's prompt on all 10. Save outputs. Read them yourself.
**DONE WHEN:** 10 output files, plus a note of which are wrong.

### Day 10 — Thu 20 Aug
**LEARN (30 min):** Search "golden dataset LLM eval." An eval needs a known-correct answer.
**BUILD (60 min):** Label all 10 `good`/`bad`/`borderline` with a one-line reason each.
**DONE WHEN:** all 10 labeled. This is your ground truth.

### Day 11 — Fri 21 Aug
**BUILD (90 min):** Four hard assertions: valid JSON? all fields present? non-empty? under N tokens? Run on all 10.
**DONE WHEN:** a 10×4 pass/fail table.

### Day 12 — **Sat 22 Aug — `/advanced-learn` SESSION 2** (4 hrs)

```
/advanced-learn LLM-as-a-judge evaluation

Context: QA engineer, 3 years, building an eval harness for LLM-generated test
cases. I have 10 labeled examples (my own human labels as ground truth) and four
deterministic assertions already running. Now I need to build a model-graded judge
and — more importantly — understand how much to trust it. I want to know the real
failure modes: position bias, self-preference, verbosity bias, rubric design, and
how people actually measure judge reliability against human labels. My QA instinct
says "the measuring instrument needs calibrating too" — teach me whether that
instinct is right and how to act on it.
```

**DONE WHEN:** 10 judge verdicts saved alongside your 10 human labels.

### Day 13 — Sun 23 Aug — **BUFFER**

### Day 14 — Mon 24 Aug
**BUILD (90 min):** Compare judge verdicts vs your labels. Confusion matrix by hand. Write down every disagreement and why.
**DONE WHEN:** you have an agreement percentage and a written disagreement list.
*Highest-value exercise in Phase 1. Almost nobody building GenAI tools does this.*

---

# WEEK 3 — Make the judge less wrong
*25–31 August*

### Day 15 — Tue 25 Aug
**BUILD (90 min):** Rewrite the judge with an explicit named-criteria rubric, not "is this good?" Save as `judge_v2.txt`. Keep v1.
**DONE WHEN:** both versions exist side by side.

### Day 16 — Wed 26 Aug
**BUILD (90 min):** Run v2 on all 10. Recompute agreement.
**DONE WHEN:** you can state both numbers, v1 and v2.

### Day 17 — Thu 27 Aug
**BUILD (90 min):** Expand to 30 requirements. Include 5 adversarial: vague ("test the login"), contradictory, missing preconditions.
**DONE WHEN:** 30 exist, 5+ adversarial, all labeled.

### Day 18 — Fri 28 Aug
**BUILD (90 min):** Run everything on all 30.
**DONE WHEN:** agreement recalculated on 30.

### Day 19 — Sat 29 Aug (4 hrs) — *no session, this is applied MSc material*
**LEARN (45 min):** Frame precision/recall for evals specifically — what's a false positive when grading test cases?
**BUILD (3 hrs):** Compute precision and recall for your judge against your labels. Put the numbers in the README.
**DONE WHEN:** README has a real metrics table.

### Day 20 — Sun 30 Aug — **BUFFER**

### Day 21 — Mon 31 Aug
**BUILD (90 min):** Write the harness README *before* the code. What does the CLI take, what does it output?
**DONE WHEN:** README describes a tool that doesn't exist yet.

---

# WEEK 4 — Build the harness
*1–7 September*

### Day 22 — Tue 1 Sep
**BUILD (90 min):** Dataset loader. YAML → typed Pydantic objects. Malformed file handled cleanly.
**DONE WHEN:** broken YAML gives a readable error, not a stack trace.

### Day 23 — Wed 2 Sep
**BUILD (90 min):** Runner. Prompt against every case. API errors and rate limits handled with retry + backoff.
**DONE WHEN:** a 30-case run completes even when some calls fail.

### Day 24 — Thu 3 Sep
**BUILD (90 min):** Scorer. Assertion-scoring and judge-scoring pluggable behind one interface.
**DONE WHEN:** you can run assertions-only, judge-only, or both, via a flag.

### Day 25 — Fri 4 Sep
**BUILD (90 min):** Reporter. Pass rate, total cost, mean latency, every failure with its reason.
**DONE WHEN:** one command gives a readable report.

### Day 26 — Sat 5 Sep (4 hrs) — *no session, this is your home turf*
**BUILD (4 hrs):** Save results to `baseline.json`. Diff subsequent runs against it, flag regressions. The hard part: what counts as a regression when outputs are non-deterministic? Use pass-rate thresholds, not exact match.
**DONE WHEN:** deliberately worsening the prompt makes the tool report a regression.

### Day 27 — Sun 6 Sep — **BUFFER**

### Day 28 — Mon 7 Sep
**BUILD (90 min):** Use the harness on yourself. Improve Day 7's prompt based only on what the tool says. Re-run.
**DONE WHEN:** before/after numbers from a change the tool told you to make.

---

# WEEK 5 — Ship it
*8–13 September*

### Day 29 — Tue 8 Sep
**LEARN (40 min):** GitHub Actions "Quickstart" and "Using secrets."
**BUILD (50 min):** Workflow running the harness on every push. Key as repo secret.
**DONE WHEN:** a push triggers a green run.

### Day 30 — Wed 9 Sep
**BUILD (90 min):** CI fails when pass rate drops below your threshold.
**DONE WHEN:** pushing a bad prompt turns CI red.
*This is an AI quality gate — Nagam's point, in its smallest working form.*

### Day 31 — Thu 10 Sep
**BUILD (90 min):** Cost guardrail. Abort if projected spend exceeds cap. Fail loud.
**DONE WHEN:** cap at $0.001 causes a clean abort with a clear message.

### Day 32 — Fri 11 Sep
**BUILD (90 min):** Tests for the harness itself. Mock the API — don't burn tokens in unit tests.
**DONE WHEN:** `pytest` passes with no network access.

### Day 33 — Sat 12 Sep (4 hrs)
**BUILD (4 hrs):** Final README — problem, approach, how to run, example output, Day 19 metrics table. Then 400–600 words on the Day 14 finding: where the judge disagreed with you and why.
**DONE WHEN:** a stranger could run it from the README alone.

### Day 34 — Sun 13 Sep — **SHIP**
- [ ] Public, README complete, CI green
- [ ] Message Tejsinh and Nagam — separately, not copy-pasted. What you built, one surprise, no ask.
- [ ] Create `ambiguity-chaser` repo

---

# PHASE 2 — Ambiguity Chaser (Sep–Nov)

Week-level only. Daily detail comes when you get there — writing November's steps today would be fiction.

**Week 6** — LangGraph fundamentals → **SESSION 3**
**Week 7** — Port Phase 1 prompt into a single-node graph
**Week 8** — Conditional edges: score → "emit spec" or "ask questions"
**Week 9** — Human-in-the-loop interrupt → **SESSION 4**
**Week 10** — Re-ask loop + max-iteration guard
**Week 11** — Tool calling: coverage check
**Week 12** — Embeddings + retrieval → **SESSION 5**
**Week 13** — Schema-validated spec emission
**Week 14** — Point the Phase 1 harness at the agent
**Week 15** — Polish, ship, second message to seniors

### SESSION 3 prompt — Week 6, Saturday

```
/advanced-learn LangGraph for building stateful agents

Context: QA automation engineer, Java/Selenium background, just shipped an LLM eval
harness in Python so I'm comfortable with API calls, Pydantic and structured output.
I've never built an agent. I'm building a system where an agent reads a vague
software requirement, scores how testable it is, and either emits a structured test
spec or generates clarifying questions and waits for a human answer before
continuing. I need to understand nodes, edges, and state properly — not a toy
chatbot demo. Tell me what to ignore in the LangGraph docs, because I know there's a
lot there I don't need yet.
```

### SESSION 4 prompt — Week 9, Saturday

```
/advanced-learn human-in-the-loop interrupts and state persistence in LangGraph

Context: I have a working LangGraph agent with conditional edges that scores
requirement testability. Now the hard part: when the score is low, the graph must
pause, surface clarifying questions to a human, wait — possibly for hours — and then
resume with state intact. I need checkpointing, interrupt patterns, and how state
survives a process restart. I'm a QA engineer so I care a lot about the failure
modes: what happens if the process dies mid-pause, and how do I test a graph that's
designed to stop halfway.
```

### SESSION 5 prompt — Week 12, Saturday

```
/advanced-learn embeddings and retrieval quality measurement

Context: QA engineer building an agent that checks whether a new requirement is
already covered by an existing test case. I need semantic search over a corpus of a
few hundred test cases. I have an MSc in ML so I understand vector spaces and
cosine similarity conceptually — what I don't have is practical judgment: which
embedding model, chunking strategy for short structured text, and above all how to
*measure* whether retrieval is actually good rather than assuming it is. Treat
retrieval precision as something to be tested, not trusted.
```

---

# PHASE 3 — Agent Eval Layer (Dec–Jan)

**Weeks 16–17** — Labeled dataset, 300+ requirements
**Week 18** — Train the classifier → **SESSION 6** *(GPU needed)*
**Week 19** — Benchmark: classifier vs LLM judge — accuracy, latency, cost
**Week 20** — Confidence routing: cheap first, escalate on uncertainty
**Week 21** — Cluster historical failures (data mining)
**Week 22** — Trajectory evaluation → **SESSION 7**
**Week 23** — Deploy: cloud, containers, CI/CD (Nagam's DevOps note)
**Week 24** — Write-up. Soloship gate interface if still wanted. **Final message to seniors — this is when you ask about openings.**

### SESSION 6 prompt — Week 18, Saturday

```
/advanced-learn fine-tuning a small transformer classifier on a custom text dataset

Context: MSc in ML so the theory is not the gap — I understand transformers,
backprop, overfitting. The gap is practical execution. I have ~300 labeled software
requirements tagged for testability and want to fine-tune a small encoder model to
classify them, then benchmark it against an LLM-as-judge baseline on accuracy,
latency and cost. Hardware is a single RTX 4050 with 6GB VRAM, which I suspect is
the real constraint shaping every decision here. Tell me what actually fits, what
to cut, and where 300 examples will bite me.
```

### SESSION 7 prompt — Week 22, Saturday

```
/advanced-learn evaluating agent trajectories rather than final outputs

Context: I've built a multi-step LangGraph agent and an eval harness, and I've hit
the limit of output-only evaluation — the agent can reach a correct answer via a
terrible path (unnecessary tool calls, redundant loops, wasted spend) and my eval
scores it as a pass. I'm a QA engineer; this feels like testing only the return
value while ignoring the call stack. I want to know how people actually score the
path: step-level assertions, tool-choice correctness, loop detection, and whether
there's any accepted methodology here or if it's still an open problem.
```

---

## Why only seven sessions

The skill earns its keep on topics with **non-obvious traps** — judge bias, graph state, VRAM limits. It's wasted on doc-reading (API pages, pricing, Click, GitHub Actions), and it's wasted on things you already know from QA and the MSc (regression baselines, precision/recall, test design). Firing it at everything would turn it into background noise.

---

## Red flags

- **13 Sep and P1 isn't shipped** → stop, finish P1, delay everything
- **Redesigning something that already works** → scope creep
- **Three buffer days in a row spent catching up** → budget's wrong, cut to 1 hr/day, don't abandon
- **Starting P2 before P1 is public** → the exact pattern that has killed previous projects

---

## The story this builds toward

> "I came from QA automation and noticed nobody was applying QA rigor to AI systems themselves. I built an eval harness first, then an agent, then used the harness to evaluate the agent. Along the way a fine-tuned classifier matched LLM-as-judge accuracy at a fraction of the cost — so I routed cheap-first and escalated on low confidence."

Not a skills list. A narrative.
