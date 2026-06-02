"""环境变量与运行时 DEFAULTS。

环境变量从 `.env` 读取；DEFAULTS 是 `setting` 表首次启动时的种子，
后续以 DB 为准。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SB2099_ADMIN_TOKEN: str = Field(..., min_length=6)
    SB2099_IP_SALT: str = Field(..., min_length=8)
    DOUYU_ROOM_ID: int = 12740109
    SB2099_DB_PATH: str = "./sb2099.db"

    @property
    def db_url(self) -> str:
        p = Path(self.SB2099_DB_PATH).resolve()
        return f"sqlite:///{p.as_posix()}"

    @property
    def async_db_url(self) -> str:
        p = Path(self.SB2099_DB_PATH).resolve()
        return f"sqlite+aiosqlite:///{p.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


# setting 表首次启动种子值；后续以 DB 为准
DEFAULTS: dict[str, object] = {
    "live_hot_min_unique_senders_24h": 20,
    "live_hot_min_length": 2,
    "live_hot_max_length": 80,
    "live_noise_filters": ["晚安", "88888", "爆了", "+1"],
    "live_suffix_strips": ["喵", "Oᴗoಣ"],
    "submission_review_rules": [],
    "barrage_min_length": 4,
    "barrage_max_length": 255,
    "ratelimit_submit_per_hour_per_ip": 5,
    "ratelimit_submit_signed_per_hour_per_ip": 30,
    "ratelimit_report_per_hour_per_ip": 60,
    "ratelimit_copy_per_hour_per_ip": 200,
    "ratelimit_promote_per_hour_per_ip": 5,
    "raw_retention_days": 2,
    "daily_hot_retention_days": 7,
    "submission_anti_fraud_enabled": True,
    "submission_uid_multi_ip_window_days": 7,
    "submission_uid_multi_ip_threshold": 5,
    "submission_uid_inactive_days": 30,
    "submission_uid_unseen_blocks": True,
    "submission_withdraw_window_seconds": 60,
}


INITIAL_TAGS: list[dict[str, object]] = [
    {"value": "00", "label": "主播", "icon_url": None, "sort": 0, "enabled": 1},
    {"value": "01", "label": "选手", "icon_url": None, "sort": 1, "enabled": 1},
    {"value": "02", "label": "互动", "icon_url": None, "sort": 2, "enabled": 1},
    {"value": "99", "label": "其他", "icon_url": None, "sort": 99, "enabled": 1},
]
