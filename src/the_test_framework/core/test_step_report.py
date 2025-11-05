from __future__ import annotations

from dataclasses import dataclass
import datetime
from logging import LogRecord
from typing import Any

from .dtypes import TestResult, ExcInfo


@dataclass
class TestStepReport:
    name: str
    test_result: TestResult
    start_time: datetime.datetime
    end_time: datetime.datetime
    log_messages: list[LogRecord]
    children: list[TestStepReport]
    parent: TestStepReport | None
    return_value: Any
    exc_info: ExcInfo | None
