"""配置：环境变量优先，模型配置也可从 starter/.env 读取。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

#: 契约规定：系统的“今天”固定为 2026-09-01。
#: 允许用环境变量覆盖，只为测试留一个口子，默认值就是契约值。
DEFAULT_TODAY = "2026-09-01"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent


def _default_workspace() -> Path:
    """data/ 与 knowledge_base/ 在本项目的上一层。"""
    return PROJECT_DIR.parent


def _path_from_env(name: str, fallback: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser().resolve() if raw else fallback.resolve()


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    kb_dir: Path
    var_dir: Path
    today: date
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: float
    chat_budget: float

    @property
    def source_db(self) -> Path:
        return self.data_dir / "pos.db"

    @property
    def clean_db(self) -> Path:
        return self.var_dir / "clean.db"

    @property
    def index_path(self) -> Path:
        # 索引缓存跟着仓库走，clone 下来就能直接起服务，不用等建索引。
        return PROJECT_DIR / ".cache" / "index.json"

    @property
    def live(self) -> bool:
        """契约 §7.2：没有 Key 就进入 mock 降级模式，服务照常启动。"""
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)

    @property
    def llm_mode(self) -> str:
        return "live" if self.live else "mock"


def load_settings() -> Settings:
    workspace = _default_workspace()
    file_config = dotenv_values(PROJECT_DIR / ".env")

    def llm_value(name: str, default: str = "") -> str:
        value = os.environ.get(name, file_config.get(name))
        return default if value is None else str(value).strip()

    return Settings(
        data_dir=_path_from_env("DATA_DIR", workspace / "data"),
        kb_dir=_path_from_env("KB_DIR", workspace / "knowledge_base"),
        var_dir=_path_from_env("VAR_DIR", PROJECT_DIR / "var"),
        today=date.fromisoformat(os.environ.get("TODAY", DEFAULT_TODAY)),
        # 地址原样使用：不补 /v1，不截路径（契约 §7.2）。
        llm_base_url=llm_value("LLM_BASE_URL").rstrip("/"),
        llm_api_key=llm_value("LLM_API_KEY"),
        llm_model=llm_value("LLM_MODEL"),
        # 契约 §7.3：单次模型调用超时不小于 120 秒。
        llm_timeout=float(llm_value("LLM_TIMEOUT", "120")),
        # 契约 §7.3：/api/chat 整体在 180 秒内返回，这里留出余量。
        chat_budget=float(llm_value("CHAT_BUDGET", "150")),
    )
