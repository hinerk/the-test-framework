from __future__ import annotations

import datetime
from typing import Callable, Any, TYPE_CHECKING

from log_capture import LogCapture


from .metadata import TestStepMetadata, TestStepMetadataControl


if TYPE_CHECKING:
    from .decorated_test_step import DecoratedTestStep


class TestStepSupervision:
    """Context Manager which tracks progress, potential exceptions and
    the return value of a TestStep"""
    def __init__(
            self,
            log_capture: LogCapture,
            metadata: TestStepMetadata,
            metadata_ctrl: TestStepMetadataControl,
            on_enter_callback: Callable[[], None],
            on_exit_callback: Callable[[], None],
    ):
        self._log_capture = log_capture
        self._metadata = metadata
        self._metadata_ctrl = metadata_ctrl
        self._on_enter_callback = on_enter_callback
        self._on_exit_callback = on_exit_callback

        self._traversed_context = False
        self._submitted_return_value = False

    def __enter__(self):
        self._log_capture.__enter__()
        self._on_enter_callback()
        self._metadata_ctrl.submit_test_start_time(datetime.datetime.now())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._metadata_ctrl.submit_test_end_time(datetime.datetime.now())
        self._log_capture.__exit__(exc_type, exc_val, exc_tb)
        self._traversed_context = True
        self._metadata_ctrl.submit_exception_info(exc_val)
        self._metadata_ctrl.submit_log_messages(self._log_capture.records)
        self._attempt_to_complete()
        self._on_exit_callback()

    def _attempt_to_complete(self):
        """completes associated TestStepMetadata object if precondition is met

        Completes the associated TestStepMetadata object if the context was
        traversed and the TestSteps return data was submitted.
        """
        if self._submitted_return_value and self._traversed_context:
            self._metadata_ctrl.complete()

    def submit_return_value(self, return_value: Any):
        """submit the return value of the call of the supervised TestStep"""
        self._metadata_ctrl.submit_return_value(return_value)
        self._submitted_return_value = True
        self._attempt_to_complete()

    @property
    def metadata(self) -> TestStepMetadata:
        """access TestStepMetadata of supervised TestStep"""
        return self._metadata


class TestStepSupervisor:
    """TestSystem Internal Logic to supervise test step execution"""
    def __init__(
            self,
            on_test_step_enter_callback: Callable[[
                TestStepMetadata], None] | None = None,
            on_test_step_exit_callback: Callable[[
                TestStepMetadata], None] | None = None,
    ):
        self._on_test_step_enter_callback = on_test_step_enter_callback
        self._on_test_step_exit_callback = on_test_step_exit_callback

        self._log_capture = LogCapture()
        self._test_step_stack: list[TestStepMetadata] = list()
        self._supervision_registry: dict[
            TestStepMetadata, TestStepSupervision] = dict()

        # TestStepMetadata for the most recently finished TestStep:
        self._latest_test_step: TestStepMetadata | None = None

        # TestStepMetadata for the most recently finished root TestStep
        # (one without parent test step)
        self._latest_root_test_step: TestStepMetadata | None = None

        # stores the TestStepMetadata objects of each root TestStep (not
        # covering embedded ones, as those can be accessed via their root):
        self._sequence: list[TestStepMetadata] = list()

    def supervise_test_step(
            self, test_step: DecoratedTestStep,
    ) -> TestStepSupervision:
        """registers a DecoratedTestStep for supervision during execution

        :param test_step: Test step to supervise
        :returns: TestStepSupervision: test step supervision context manager.
        """
        metadata, metadata_ctrl = TestStepMetadata.create_controlled_metadata(
            parent=self.active_test_step,
            function=test_step)

        def on_test_step_enter_callback():
            self._test_step_stack.append(metadata)
            if self._on_test_step_enter_callback is not None:
                self._on_test_step_enter_callback(metadata)

        def on_test_step_exit_callback():
            assert self._test_step_stack[-1] == metadata
            self._latest_test_step = self._test_step_stack.pop()
            if len(self._test_step_stack) == 0:
                self._latest_root_test_step = self._latest_test_step
            if self._on_test_step_exit_callback is not None:
                self._on_test_step_exit_callback(metadata)

        test_step_supervision = TestStepSupervision(
            log_capture=self._log_capture,
            metadata=metadata,
            metadata_ctrl=metadata_ctrl,
            on_enter_callback=on_test_step_enter_callback,
            on_exit_callback=on_test_step_exit_callback,
        )
        self._supervision_registry[metadata] = test_step_supervision
        return test_step_supervision

    @property
    def active_test_step(self) -> TestStepMetadata | None:
        """get the currently active TestStep's metadata"""
        if self._test_step_stack:
            return self._test_step_stack[-1]
        return None

    @property
    def latest_test_step(self) -> TestStepMetadata | None:
        """get TestStepMetadata for the most recently finished TestStep"""
        return self._latest_test_step

    @property
    def latest_root_test_step(self) -> TestStepMetadata | None:
        """get TestStepMetadata for the most recently finished root TestStep"""
        return self._latest_root_test_step
