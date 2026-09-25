import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float = 60.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def load_settings(env: dict[str, str] | None = None, env_file: Path | None = None) -> Settings:
    values = dict(os.environ if env is None else env)
    file_path = env_file or Path(__file__).resolve().parents[2] / ".env"
    if file_path.exists():
        for line in file_path.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key and key not in values:
                values[key] = value
    timeout = float(values.get("DEEPSEEK_TIMEOUT_SECONDS", "60"))
    if not 0 < timeout <= 600:
        raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be between 0 and 600")
    return Settings(
        api_key=values.get("DEEPSEEK_API_KEY", "").strip(),
        base_url=values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        model=values.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        timeout_seconds=timeout,
    )
