import os
from dataclasses import dataclass
from pathlib import Path

from . import rules


_REMOVED_RULE_KEYS = {'BASELINE_THINKING', 'JUDGE_THINKING', 'JUDGE_SAMPLES'}


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 240.0
    baseline_thinking: str = rules.BASELINE['generation_thinking']
    judge_thinking: str = rules.JUDGE['thinking']
    judge_samples: int = rules.JUDGE['samples']

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def load_values(env: dict[str, str] | None = None, env_file: Path | None = None) -> dict:
    values = dict(os.environ if env is None else env)
    file_path = env_file or Path(os.getenv("RAG_DEMO_ENV_PATH") or Path(__file__).resolve().parents[2] / ".env")
    if file_path.exists():
        for line in file_path.read_text().splitlines():
            key, separator, value = line.partition("=")
            key = key.strip().removeprefix('export ').strip()
            if separator and key in _REMOVED_RULE_KEYS:
                raise ValueError(f'{key}：规则项已移到 rules.py，请从 .env 删除')
            if separator and key and key not in values and not key.startswith('#'):
                values[key] = value
    return values


def load_settings(env: dict[str, str] | None = None, env_file: Path | None = None) -> Settings:
    values = load_values(env, env_file)
    timeout = float(values.get("DEEPSEEK_TIMEOUT_SECONDS", "240"))
    if not 0 < timeout <= 600:
        raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be between 0 and 600")
    model = values.get("DEEPSEEK_MODEL", "deepseek-flash")
    if model == "deepseek-v4-flash": model = "deepseek-flash"
    return Settings(
        api_key=values.get("DEEPSEEK_API_KEY", "").strip(),
        base_url=values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        model=model,
        timeout_seconds=timeout,
    )
