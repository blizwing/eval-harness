"""
Day 2 — Temperature and non-determinism.

Goal: run the same prompt 10x at temperature=0 and 10x at temperature=1,
for BOTH schemas, and be able to state from the data whether temp=0 gave
identical output every time.

Reuses Day 1's call functions (parameterized with temperature) rather than
duplicating client setup — see Day1_first_call.py.

Output: results saved to temp0_runs_*.txt / temp1_runs_*.txt (one file per
schema per temperature) so you can diff them manually as the roadmap asks,
plus a quick automated uniqueness count as a sanity check before you go
read them by eye.
"""

from collections import Counter
from Day1_first_call import callAnthropicSchemaAPI, callOpenAISchemaAPI, DEEPSEEK_API_KEY

N_RUNS = 10
PROMPT = "Write a haiku about testing."

def run_batch(call_fn, temperature: float, n: int = N_RUNS) -> list[str]:
    """Call the given schema function n times at a fixed temperature, return the texts."""
    outputs = []
    for i in range(n):
        result = call_fn(prompt=PROMPT, temperature=temperature)
        outputs.append(result.text)
        print(f"  run {i + 1}/{n} done")
    return outputs

def save_and_summarize(label:str, outputs:list[str], filepath:str) -> None:
    """Write all outputs to a file, then print a uniqueness summary to terminal."""
    with open(filepath, "w", encoding="utf-8") as f:
        for i, text in enumerate(outputs, start=1):
            f.write(f"--- run {i} ---\n{text}\n\n")

    unique_count = len(set(outputs))
    print(f"\n[{label}]: {len(outputs)} runs to {filepath}")
    print(f"[{label}] unique outputs: {unique_count} / {len(outputs)}")

    if(unique_count > 1):
        counts = Counter(outputs)
        print(f"[{label}] breakdown:")
        for text, count in counts.most_common():
            preview = text.replace("\n", " / ")[:50]
            print(f"    x{count}: {preview}...")


def main() -> None:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set — check your .env")

    for schema_name, call_fn in (
        ("anthropic", callAnthropicSchemaAPI),
        ("openai", callOpenAISchemaAPI),
    ):
        print(f"\n{'=' * 60}")
        print(f"SCHEMA: {schema_name}")
        print("=" * 60)

        print(f"\nRunning {N_RUNS}x at temperature=0")
        temp0_outputs = run_batch(call_fn, temperature=0)
        save_and_summarize(
            f"{schema_name} / temp=0",
            temp0_outputs,
            f"temp0_runs_{schema_name}.txt",
        )

        print(f"\nRunning {N_RUNS}x at temperature=1")
        temp1_outputs = run_batch(call_fn, temperature=1)
        save_and_summarize(
            f"{schema_name} / temp=1",
            temp1_outputs,
            f"temp1_runs_{schema_name}.txt",
        )


if __name__ == "__main__":
    main()