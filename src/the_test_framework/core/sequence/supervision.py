from __future__ import annotations

import functools

from typing import Any, TYPE_CHECKING

from log_capture import LogCapture

from ..dtypes import TestResult, TestResultInfo
from ..test_step.helpers import infer_test_result
from ..test_step.metadata import TestStepMetadata
from ..test_step.supervision import TestStepSupervisor


if TYPE_CHECKING:
    pass


class TestSequenceSupervision:
    """Context Manager which supervises Test Sequence execution"""
    @classmethod
    def setup_supervision(
            cls,
            log_capture: LogCapture | None = None
    ) -> tuple[TestSequenceSupervision, TestStepSupervisor]:
        """creates entangled TestStepSupervision and TestStepSupervisor"""
        sequence_supervision = cls()

        def submit_test_step_meta_data(metadata: TestStepMetadata):
            """submit new TestStepMetadata to SequenceSupervision"""
            if metadata.parent is not None:
                return
            sequence_supervision._sequence.append(metadata)

        step_supervisor = TestStepSupervisor(
            on_test_step_enter_callback=submit_test_step_meta_data,
            log_capture=log_capture,
        )
        return sequence_supervision, step_supervisor


    def __init__(self):
        self._sequence: list[TestStepMetadata] = list()

        # the test sequence's return value:
        self._return_value: Any = None

        # whether the test sequence return value was already submitted
        self._submitted_return_value = False

        # whether context was traversed
        self._traversed_context = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._traversed_context = True

    def submit_return_value(self, return_value: Any):
        self._return_value = return_value
        self._submitted_return_value = True

    @property
    def test_result(self) -> TestResult:
        """get the overall result of the Test Sequence"""
        if not self._traversed_context:
            raise RuntimeError("Test Sequence not yet finished!")
        if not self._submitted_return_value:
            raise RuntimeError("return value of Test Sequence is not yet submitted!")

        sequence_results = [t.test_result for t in self._sequence]
        inferred_result = infer_test_result(self._return_value)

        return functools.reduce(lambda a, b: a.merge(b),
                                [*sequence_results, inferred_result])

    @property
    def test_result_info(self) -> TestResultInfo:
        return TestResultInfo(steps=[ts.as_test_step_result_info()
                                     for ts in self.metadata])

    @property
    def return_value(self) -> Any:
        if not self._submitted_return_value:
            raise RuntimeError("No return value submitted!")
        return self._return_value

    @property
    def metadata(self) -> list[TestStepMetadata]:
        return self._sequence
