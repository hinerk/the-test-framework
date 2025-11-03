from contextlib import ExitStack
from typing import (
    Any,
    Annotated,

)
from the_test_framework.core.dtypes import TestResultInfo
from the_test_framework.core.arg_flags import (
    IsSystemSetupData,
    IsTestSequenceData,
    IsUUTSetupData,
)
from .abstract_callback import RegisteredCallback


class SystemSetupCallback(RegisteredCallback):
    description = "System Setup"
    mandatory = False

    def __call__(self, exit_stack: ExitStack) -> Any:
        return super()._invoke(exit_stack=exit_stack)


class TestBedPreparationCallback(RegisteredCallback):
    description = "Test Bed Preparation"
    mandatory = False
    def __call__(
            self,
            system_setup_data: Annotated[Any, IsSystemSetupData],
    ) -> Any:
        return super()._invoke(system_setup_data=system_setup_data)


class UUTSetupCallback(RegisteredCallback):
    description = "UUT Setup"
    mandatory = False

    def __call__(
        self,
        system_setup_data: Annotated[Any, IsSystemSetupData],
        exit_stack: ExitStack,
    ) -> Any:
        return super()._invoke(system_setup_data=system_setup_data,
                               exit_stack=exit_stack)


class TestSequenceCallback(RegisteredCallback):
    description = "Test Sequence"
    mandatory = True

    def __call__(
        self,
        system_setup_data: Annotated[Any, IsSystemSetupData],
        uut_setup_data: Annotated[Any, IsUUTSetupData],
    ) -> Any:
        return super()._invoke(system_setup_data=system_setup_data,
                               uut_setup_data=uut_setup_data)


class UUTRecoveryCallback(RegisteredCallback):
    description = "UUT Recovery"
    mandatory = False
    def __call__(
        self,
        system_setup_data: Annotated[Any, IsSystemSetupData],
        uut_setup_data: Annotated[Any, IsUUTSetupData],
        test_sequence_data: Annotated[Any, IsTestSequenceData],
        test_result: TestResultInfo,
    ) -> Any:
        return super()._invoke(system_setup_data=system_setup_data,
                               uut_setup_data=uut_setup_data,
                               test_sequence_data=test_sequence_data,
                               test_result=test_result)


class UUTResultHandlerCallback(RegisteredCallback):
    description = "UUT Result Handler"
    mandatory = False

    def __call__(
        self,
        system_setup_data: Annotated[Any, IsSystemSetupData],
        uut_setup_data: Annotated[Any, IsUUTSetupData],
        test_sequence_data: Annotated[Any, IsTestSequenceData],
        test_result: TestResultInfo,
    ) -> Any:
        return super()._invoke(system_setup_data=system_setup_data,
                               uut_setup_data=uut_setup_data,
                               test_sequence_data=test_sequence_data,
                               test_result=test_result)
