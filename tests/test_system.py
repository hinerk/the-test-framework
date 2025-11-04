from contextlib import ExitStack
from typing import Annotated
from dataclasses import dataclass

import pytest

from the_test_framework.core import (
    TestSystem,
    IsSystemSetupData,
    IsUUTSetupData,
    IsTestSequenceData,
    TestResultInfo,
)
from the_test_framework.core.exceptions import (
    QuitTestSystem,
    TestSystemIntrospectionError,
)


def pytest_requesting_data():
    """test requesting data via registered callback signatures"""
    test_system = TestSystem()

    @dataclass
    class SystemSetupData: ...

    @dataclass
    class UUTSetupData: ...

    @dataclass
    class TestSequenceData: ...

    @test_system.system_setup
    def system_setup() -> SystemSetupData:
        return SystemSetupData()

    @test_system.test_bed_preparation
    def test_bed_preparation(
            system_setup: Annotated[SystemSetupData, IsSystemSetupData],
    ):
        assert isinstance(system_setup, SystemSetupData)

    state = {"terminate": False}

    @test_system.uut_setup
    def uut_setup(
            system_setup: Annotated[SystemSetupData, IsSystemSetupData],
            exit_stack: ExitStack,
    ):
        if state["terminate"]:
            raise QuitTestSystem()
        state["terminate"] = True
        assert isinstance(system_setup, SystemSetupData)
        assert isinstance(exit_stack, ExitStack)
        return UUTSetupData()

    @test_system.uut_result_handler
    def uut_result_handler(
            system_setup: Annotated[SystemSetupData, IsSystemSetupData],
            uut_setup: Annotated[UUTSetupData, IsUUTSetupData],
            sequence_data: Annotated[TestSequenceData, IsTestSequenceData],
            test_result: TestResultInfo,
    ):
        assert isinstance(system_setup, SystemSetupData)
        assert isinstance(uut_setup, UUTSetupData)
        assert isinstance(sequence_data, TestSequenceData)
        assert isinstance(test_result, TestResultInfo)

    @test_system.test_sequence
    def main_sequence():
        return TestSequenceData()

    test_system()


def pytest_missing_registered_procedure_callback():
    """test what happens when test_system.test_sequence is not registered"""
    test_system = TestSystem()

    with pytest.raises(TestSystemIntrospectionError):
        test_system()
