from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from crawler.config import Settings


def load_settings(env_path: Optional[str] = None) -> Settings:
    # 统一加载 .env 并构建 Settings，避免脚本内重复逻辑
    project_root = Path(__file__).resolve().parent.parent
    env_file = Path(env_path) if env_path else project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()
    return Settings.from_env()
