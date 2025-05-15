# 📦 minimal‑myaa ─ LangGraph × Discord (Starter Kit)

---

## 🗂️ Directory Layout

```text
myaa/                    # <repo root>
├── README.md            # quick-start instructions
├── .env.example         # copy to .env and set secrets
├── pyproject.toml       # project metadata and deps
└── myaa/                # main Python package
    ├── __init__.py
    ├── adapter/         # Discord I/O, etc
    ├── logic/           # core agent logic (LangGraph etc)
    ├── tools/           # tool invocation layer (TBD)
    └── data/            # cache/memory modules (TBD)
```

---

## 🚀 Usage (For Users)

```bash
# 1. Create virtual environment
uv venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install dependencies
uv pip install -e .

# 3. Set your secrets
cp .env.example .env
# Then edit .env to include your Discord bot token and OpenAI API key

# 4. Run the bot
uv run run-bot
```

---

## 🛠️ Dev Workflow (For Developers)

This project uses a portable Python-based `dev.py` script instead of shell commands or Makefile,
so it works on both **Linux/macOS and Windows environments** out of the box.

```bash
# 1. Install dev tools
uv pip install -e .[dev]

# 2. Run dev tasks via Python
python dev.py lint           # Run ruff linter
python dev.py fix            # Auto-fix lint issues (ruff --fix)
python dev.py format         # Format code using black
python dev.py check-format   # Check format without modifying
python dev.py test           # Run pytest
