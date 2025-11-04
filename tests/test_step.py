import pytest
from the_test_framework.core import test_step, TestSystem, QuitTestSystem


@pytest.fixture(name="test_system")
def get_basic_test_system() -> TestSystem:
    """test system, which terminates after one run of sequence

    test_system.sequence is not yet registered!
    """
    test_system = TestSystem()

    state = {"terminate": False}

    @test_system.uut_setup
    def uut_setup():
        if state["terminate"]:
            raise QuitTestSystem()
        state["terminate"] = True
    return test_system



def pytest_test_step(test_system: TestSystem):
    @test_step(name="Some Test")
    def some_test(): return 1337

    assert some_test() == 1337

    @test_system.test_sequence
    def sequence():
        some_test()

    test_system()
