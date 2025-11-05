import functools
from dataclasses import dataclass

from . import TestResult
from .test_step_report import TestStepReport


@dataclass
class TestSequenceReport:
    steps: list[TestStepReport]

    @property
    def test_result(self) -> TestResult:
        return functools.reduce(lambda a, b: a.merge(b),
                                [s.test_result for s in self.steps])
