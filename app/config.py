"""Runtime configuration: API key and per-step model IDs from env / .env.

No python-dotenv dependency — a .env file (gitignored) is parsed with a
few lines; real environment variables always win over .env entries.
"""

import os
from pathlib import Path

# Per pipeline step; override via APPLYOS_MODEL_<STEP>. Analyze is plain
# extraction (Haiku is enough); plan + letter carry the application quality
# (user decision: Opus).
DEFAULT_MODELS = {
    "analyze": "claude-haiku-4-5",
    "match": "claude-sonnet-5",
    "plan": "claude-sonnet-5",
    "letter": "claude-sonnet-5",
    "revise": "claude-sonnet-5",
}


def load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=value lines from .env into os.environ (existing vars win)."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def model_for(step: str) -> str:
    return os.environ.get(f"APPLYOS_MODEL_{step.upper()}", DEFAULT_MODELS[step])
