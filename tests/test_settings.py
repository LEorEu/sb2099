"""settings_cache 行为：种子 DEFAULTS 可读、invalidate 后重载。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import update

from sb2099.models import Setting


def test_defaults_loaded(tmp_db):
    from sb2099.settings import settings_cache
    settings_cache.invalidate()
    assert settings_cache.get("barrage_max_length") == 255
    assert settings_cache.get("live_noise_filters") == ["晚安", "88888", "爆了", "+1"]
    assert settings_cache.get("submission_review_rules") == []
    assert settings_cache.get("raw_retention_days") == 2


def test_invalidate_reloads(tmp_db):
    from sb2099.db import SessionLocal
    from sb2099.settings import settings_cache

    settings_cache.invalidate()
    assert settings_cache.get("barrage_max_length") == 255

    with SessionLocal() as s:
        s.execute(
            update(Setting)
            .where(Setting.key == "barrage_max_length")
            .values(value=json.dumps(500), updated_at=datetime.utcnow())
        )
        s.commit()

    # 不 invalidate：仍读到旧值（TTL 内）
    assert settings_cache.get("barrage_max_length") == 255

    # invalidate 后 → 新值
    settings_cache.invalidate()
    assert settings_cache.get("barrage_max_length") == 500


def test_missing_key_returns_default(tmp_db):
    from sb2099.settings import settings_cache
    settings_cache.invalidate()
    assert settings_cache.get("does_not_exist", "fallback") == "fallback"
