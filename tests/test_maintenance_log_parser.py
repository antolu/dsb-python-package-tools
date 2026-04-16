from __future__ import annotations

import datetime

from dsb_devtools.maintenance._types import BaseDist


def test_is_urgent_within_six_months() -> None:
    today = datetime.date(2026, 10, 1)
    dist = BaseDist(tag="2023.06", python="3.11", eol=datetime.date(2027, 1, 1))
    assert dist.is_urgent(today=today)


def test_is_urgent_more_than_six_months() -> None:
    today = datetime.date(2026, 4, 1)
    dist = BaseDist(tag="2023.06", python="3.11", eol=datetime.date(2027, 4, 1))
    assert not dist.is_urgent(today=today)


def test_is_urgent_deprecated_is_never_urgent() -> None:
    today = datetime.date(2026, 4, 1)
    dist = BaseDist(
        tag="2021.12", python="3.9", eol=datetime.date(2026, 12, 1), deprecated=True
    )
    assert not dist.is_urgent(today=today)
