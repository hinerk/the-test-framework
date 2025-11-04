from dataclasses import dataclass, field
import enum
from typing import Any, TypeAlias
from logging import LogRecord


TestStepCallID: TypeAlias = str


class TestResult(enum.Enum):
    """The Test Result of both Test Step and Test Sequence"""
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
    """A custom Test Result which allows to return a recognized TestResult
    along with data from a Test Step.

    If a Test Step is returning an instance of CustomTestResult, TestResult
    inference is bypassed and CustomTestResult.result is considered instead.
    """
    result: TestResult
    returned: T


@dataclass
class TestStepResultInfo[T]:
    """Captures the Result for a Test Step"""
    name: str
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
    """Captures the Result for a Test Sequence"""
    steps: list[TestStepResultInfo[Any]]

    def __bool__(self) -> bool:
        return all(self.steps)
