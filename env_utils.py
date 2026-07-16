import os
from pathlib import Path
from typing import Optional


def _find_env_file(start: Optional[Path] = None) -> Optional[Path]:
    base_dir = (start or Path(__file__).resolve().parent).resolve()
    for directory in [base_dir, *base_dir.parents]:
        env_path = directory / ".env"
        if env_path.is_file():
            return env_path
    return None


def load_dotenv(env_path: Optional[os.PathLike[str] | str] = None) -> bool:
    resolved_path = Path(env_path) if env_path else _find_env_file()
    if resolved_path is None or not resolved_path.is_file():
        return False

    for raw_line in resolved_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export "):]

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value

    return True


def get_hf_token(env_path: Optional[os.PathLike[str] | str] = None) -> Optional[str]:
    if os.getenv("HF_TOKEN"):
        return os.getenv("HF_TOKEN")

    load_dotenv(env_path)
    return os.getenv("HF_TOKEN")
