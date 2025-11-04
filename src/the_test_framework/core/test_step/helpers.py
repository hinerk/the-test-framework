from __future__ import annotations

from typing import Any

from ..dtypes import TestResult, CustomTestResult
from ..exceptions import FailedTest


def infer_test_result(returned: Any | None = None,
                      exc_info: BaseException | None = None) -> TestResult:
    """infers test result from return value or exception info"""
    if isinstance(returned, TestResult):
        return returned
    if isinstance(returned, CustomTestResult):
        return returned.result
    if exc_info is not None:
        if isinstance(exc_info, FailedTest):
            return TestResult.FAILED
        else:
            return TestResult.EXCEPTION
    else:
        return TestResult.SUCCESS
