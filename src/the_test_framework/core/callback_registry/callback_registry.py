from logging import getLogger
from typing import Generator

from .callbacks import (
    RegisteredCallback,
    SystemSetupCallback,
    TestBedPreparationCallback,
    UUTSetupCallback,
    UUTRecoveryCallback,
    UUTResultHandlerCallback,
    TestSequenceCallback,
)


logger = getLogger(__name__)


class CallbackRegistry:
    """Holds all callback slots and provides a quick completeness check."""
    def __init__(self):
        self.system_setup = SystemSetupCallback()
        self.test_bed_preparation = TestBedPreparationCallback()
        self.uut_setup = UUTSetupCallback()
        self.uut_recovery = UUTRecoveryCallback()
        self.test_sequence = TestSequenceCallback()
        self.uut_result_handler = UUTResultHandlerCallback()

    def __iter__(self) -> Generator[RegisteredCallback, None, None]:
        yield self.system_setup
        yield self.test_bed_preparation
        yield self.uut_setup
        yield self.uut_recovery
        yield self.test_sequence
        yield self.uut_result_handler

    def check(self) -> None:
        """Check whether all required callbacks are registered."""
        for callback in self:
            if not callback.registered:
                msg = f"No {callback.description} callback registered!"
                logger.warning(msg)
                if callback.mandatory:
                    raise RuntimeError(msg)
