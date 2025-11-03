from dataclasses import dataclass, field
import enum
from typing import Any, TypeAlias
from logging import LogRecord


TestStepCallID: TypeAlias = str


class TestResult(enum.Enum):
    SUCCESS = enum.auto()
    FAILED = enum.auto()
    EXCEPTION = enum.auto()

    def __bool__(self) -> bool:
        return self == TestResult.SUCCESS

    def merge(self, other: "TestResult") -> "TestResult":
        """merge TestResults

        TestResult.SUCCESS ^ TestResult.SUCCESS   -> TestResult.SUCCESS
        TestResult.SUCCESS ^ TestResult.FAILED    -> TestResult.FAILED
        TestResult.FAILED  ^ TestResult.EXCEPTION -> TestResult.EXCEPTION
        """
        if not isinstance(other, TestResult):
            raise TypeError(f"Expected TestResult but got {type(other)}")
        this_precedence_index = TestResultMergingPrecedence.index(self)
        other_precedence_index = TestResultMergingPrecedence.index(other)
        winning_precedence_index = max(this_precedence_index, other_precedence_index)
        winning_precedence = TestResultMergingPrecedence[winning_precedence_index]
        return TestResult(winning_precedence.value)


TestResultMergingPrecedence = [
    TestResult.SUCCESS,
    TestResult.FAILED,
    TestResult.EXCEPTION,
]


@dataclass
class CustomTestResult[T]:
    result: TestResult
    returned: T


@dataclass
class TestStepResultInfo[T]:
    name: str
    ancestry: tuple[str, ...]
    result: TestResult
    uuid: TestStepCallID
    returned: T
    log: list[LogRecord]
    embedded_results: list["TestStepResultInfo"]
    exception: Exception | None = None

    def __bool__(self) -> bool:
        return self.result == TestResult.SUCCESS


@dataclass
class TestResultInfo:
    steps: list[TestStepResultInfo[Any]]

    def __bool__(self) -> bool:
        return all(self.steps)
