# Getting Started

Setup steps to run this project locally.

## 1. Clone and enter the project

```bash
git clone <repo-url>
cd eval-harness
```

## 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Set up environment variables

Copy the example file and fill in your DeepSeek API key.

```bash
cp .env.example .env
```

Then open `.env` and set:

```
DEEPSEEK_API_KEY=your-key-here
```

`.env` is gitignored and should never be committed.

## 5. Run a script

Each `DayN_*.py` script is runnable standalone:

```bash
python Day1_first_call.py
```

## Project layout

- `Day1_first_call.py` — basic Anthropic-schema and OpenAI-schema calls against DeepSeek.
- `Day2_temperature.py` — non-determinism check across temperature settings.
- `Day3_llm_client.py` — `LLMClient` wrapper adding latency/cost tracking; the intended import point for later scripts.
- `Day4_json_mode.py` — JSON mode response handling.
- `NOTES.md` — day-by-day build log.
- `ROADMAP.md` — project plan and schedule.
