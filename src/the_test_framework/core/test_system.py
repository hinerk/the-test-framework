from __future__ import annotations

from typing import TYPE_CHECKING

from .sequence import TestSequenceSupervision
from .test_step.supervision import TestStepSupervisor

if TYPE_CHECKING:
    from .test_step import DecoratedTestStep

import sys
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import time
from threading import Thread
from multiprocessing import Value
from multiprocessing.sharedctypes import Synchronized
from typing import Callable, TypeVar, ParamSpec, Any, Optional
from logging import getLogger

from .exceptions import QuitTestSystem, AbortTestSequence
from .monitor import TestSystemMonitor, MonitorError
from .error_handler import error_handler
from the_test_framework.core.callback_registry import CallbackRegistry

logger = getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class SharedMemory:
    running: Synchronized


class ClusterFuckException(Exception):
    def __init__(self, errors: list[MonitorError]):
        issues = [f"    {me.origin!r} reports {me.message!r} ({me.exception!r})"
                  for me in errors]
        messages = "\n".join(["Multiple issues accumulated:", *issues])
        super().__init__(messages)


class TestSystem:
    _active_test_steps: dict[str, Any] = {}

    def __init__(self, running: Optional[Synchronized] = None):
        running = running or Value("b", True)
        self._shared_memory = SharedMemory(running=running)
        self._callback_registry = CallbackRegistry()
        self._error_handler = error_handler
        self._is_there_shit_on_the_fan = False
        self._do_not_abort = False
        self.monitor = TestSystemMonitor()
        self._quit_requested = False

        self._test_step_supervisor = TestStepSupervisor()

    def _raise_accumulated_errors(self):
        if not self.monitor.wrecked:
            return
        exc = ClusterFuckException(self.monitor.errors)
        self._error_handler(exc)
        raise exc

    # *** test_step() Decorator Callbacks *************************************
    # The TestSystem must identify test_steps within the test sequence. This
    # section of the code implements the callbacks used by the test_step()
    # decorator to provide TestSystem the necessary hooks to intercept the
    # execution of the test sequence:
    #  - prior to the execution of a test step
    #  - after the execution of a successful test step
    #  - after the execution of a failed test step
    #  - after the execution of a test interrupted by an exception
    # The mechanics must be explained, as those aren't obvious!
    # In order to allow to use a test_step with different test systems, it
    # can't be bound to a specific instance of TestSystem. To provide
    # instance-agnostic callbacks to the test_step decorator, those callbacks
    # are specified as class-methods. At runtime, a little introspection helps
    # to determine which instance of TestSystem was causing the call of the
    # class-method.

    @classmethod
    def get_active_instance(cls):
        """returns the TestSystem instance under which the call to this method was issued"""
        # Start from this frame and walk upward
        f = sys._getframe()  # deeply_hidden_callback
        while f:
            code = f.f_code
            # Look for a frame executing a __call__ method
            if code.co_name == '_test_system_exec_loop':
                # co_varnames[0] is the first positional parameter name
                if code.co_argcount >= 1:
                    first_arg = code.co_varnames[0]
                    candidate = f.f_locals.get(first_arg)
                    if isinstance(candidate, cls):
                        return candidate
            f = f.f_back
        raise RuntimeError(f"Couldn't identify {cls.__name__} instance, which"
                           f"issued the call to _find_calling_instance_()!")

    def repeat_test_step(self, step: DecoratedTestStep) -> bool:
        """framework internal method - whether the test shall be repeated"""
        self._quit_if_appropriate()
        logger.critical("_repeat_test_step is not yet implemented!")
        return False

    def _quit_if_appropriate(self):
        if self._quit_requested:
            if self._do_not_abort:
                logger.warning("test-system-exit requested while operating "
                               "under do-not-abort constraint!")
            else:
                raise QuitTestSystem()

    # *************************************************************************
    # Properties
    # *************************************************************************

    @property
    def test_step_supervisor(self) -> TestStepSupervisor:
        return self._test_step_supervisor

    @property
    def running(self):
        """whether the test loop is still running - otherwise the system is about to abort"""
        return self._shared_memory.running.value

    @running.setter
    def running(self, value):
        self._shared_memory.running.value = value

    @property
    def shared_memory(self) -> SharedMemory:
        """access the shared memory"""
        return self._shared_memory

    @contextmanager
    def never_abort(self):
        """prevent abortion with context manager

        like:

        >>> test_system = TestSystem()
        ... with test_system.never_abort():
        ...     # do stuff which shall not be aborted
        ... # do stuff which can be aborted
        """
        self._do_not_abort = True
        yield
        self._do_not_abort = False

    @property
    def do_not_abort(self):
        """whether the system shall momentarily prevent all abortion attempts"""
        return self._do_not_abort

    def restore_default_error_handler(self):
        self._error_handler = error_handler

    def error_handler(self, func: Callable[[Exception], Any]):
        """register a custom error handler (for displaying error messages)"""
        self._error_handler = func
        return func

    def quit(self):
        """quit the test system - bind this function to a GUI's exit button"""
        logger.info("abort test system")
        self._quit_requested = True

    # *************************************************************************
    # The Decorators
    # *************************************************************************

    def system_setup(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorates the function which specifies the system setup procedure.

        System setup is called once during the bring-up of the test system.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()               # this callback will be registered
            while running:
                test_bed_preparation()
                uut_setup()
                test_sequence()
                uut_recovery()
                test_result_handler()
        ```

        # Requestable Parameters

        >>> test_system = TestSystem()
        ... @test_system.system_setup
        ... def test_sequence(
        ...     exit_stack: ExitStack    # requests the system exit stack
        ... ):
        """
        self._callback_registry.system_setup.register(func)
        return func

    def test_bed_preparation(self, func: Callable[P, R]) -> Callable[P, R]:
        """Register a callback for preparing the test bed.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()
            while running:
                test_bed_preparation()   # this callback will be registered
                uut_setup()
                test_sequence()
                uut_recovery()
                test_result_handler()
        ```

        # Requestable Parameters

        >>> from typing import Annotated
        >>> from the_test_framework.core import IsSystemSetupData
        >>> test_system = TestSystem()
        ... @test_system.test_bed_preparation
        ... def test_bed_preparation(
        ...     # requests the data returned by the system setup:
        ...     system_setup: Annotated[type, IsSystemSetupData],
        ... ): ...
        """
        self._callback_registry.test_bed_preparation.register(func)
        return func

    def uut_setup(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorates the function which specifies the uut setup procedure.

        It is used to collect information like a serial number prior to the
        execution of the test sequence. the response of the function annotated
        with this decorator is fed to the test_sequence decorated function.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()
            while running:
                test_bed_preparation()
                uut_setup()              # this callback will be registered
                test_sequence()
                uut_recovery()
                test_result_handler()
        ```

        # Requestable Parameters

        >>> from typing import Annotated
        >>> from the_test_framework.core import IsSystemSetupData
        >>> test_system = TestSystem()
        ... @test_system.uut_setup
        ... def uut_setup(
        ...     # requests the data returned by the system setup:
        ...     system_setup: Annotated[type, IsSystemSetupData],
        ...     exit_stack: ExitStack  # requests the UUT exit stack
        ... ): ...
        """
        self._callback_registry.uut_setup.register(func)
        return func

    def test_sequence(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorates the function which specifies the test sequence procedure.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()
            while running:
                test_bed_preparation()
                uut_setup()
                test_sequence()          # this callback will be registered
                uut_recovery()
                test_result_handler()
        ```

        # Requestable Parameters

        >>> from typing import Annotated
        >>> from the_test_framework.core import IsSystemSetupData, IsUUTSetupData
        >>> test_system = TestSystem()
        ... @test_system.test_sequence
        ... def test_sequence(
        ...     # requests the data returned by the system setup:
        ...     system_setup: Annotated[type, IsSystemSetupData],
        ...     # requests the data returned by the UUT setup:
        ...     uut_setup: Annotated[type, IsUUTSetupData],
        ...     # requests the UUT exit stack:
        ...     exit_stack: ExitStack,
        ... ): ...
        """
        self._callback_registry.test_sequence.register(func)
        return func

    def uut_recovery(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorates the function which specifies the uut recovery procedure.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()
            while running:
                test_bed_preparation()
                uut_setup()
                test_sequence()
                uut_recovery()           # this callback will be registered
                test_result_handler()
        ```

        # Requestable Parameters

        >>> from typing import Annotated
        >>> from the_test_framework.core import (
        ...     IsSystemSetupData, IsUUTSetupData,
        ...     IsTestSequenceData, TestResultInfo
        ... )
        >>> test_system = TestSystem()
        ... @test_system.uut_recovery
        ... def uut_recovery(
        ...     # requests the data returned by the system setup:
        ...     system_setup: Annotated[type, IsSystemSetupData],
        ...     # requests the data returned by the UUT setup:
        ...     uut_setup: Annotated[type, IsUUTSetupData],
        ...     # requests the data returned by the test sequence:
        ...     sequence: Annotated[type, IsTestSequenceData],
        ...     # requests the test result info:
        ...     test_result: TestResultInfo,
        ... ): ...
        """
        self._callback_registry.uut_recovery.register(func)
        return func

    def uut_result_handler(self, func: Callable[P, R]) -> Callable[P, R]:
        """Decorates a function which handles the UUT test result.

        Can be used to shut down power supplies, print labels, commit test
        results and such.

        The following illustrates where in the test system loop the callback
        will be executed:
        ```
            system_setup()
            while running:
                test_bed_preparation()
                uut_setup()
                test_sequence()
                uut_recovery()
                test_result_handler()    # this callback will be registered
        ```

        # Requestable Parameters

        >>> from typing import Annotated
        >>> from the_test_framework.core import (
        ...     IsSystemSetupData, IsUUTSetupData,
        ...     IsTestSequenceData, TestResultInfo
        ... )
        >>> test_system = TestSystem()
        ... @test_system.uut_result_handler
        ... def uut_result_handler(
        ...     # requests the data returned by the system setup:
        ...     system_setup: Annotated[type, IsSystemSetupData],
        ...     # requests the data returned by the UUT setup:
        ...     uut_setup: Annotated[type, IsUUTSetupData],
        ...     # requests the data returned by the test sequence:
        ...     sequence: Annotated[type, IsTestSequenceData],
        ...     # requests the test result info:
        ...     test_result: TestResultInfo,
        ... ): ...
        """
        self._callback_registry.uut_result_handler.register(func)
        return func

    def _test_system_exec_loop(self):
        stack = ExitStack()
        try:
            system_setup_data = self._callback_registry.system_setup(exit_stack=stack)

            while self.running:
                self._raise_accumulated_errors()

                self._callback_registry.test_bed_preparation(
                    system_setup_data=system_setup_data)

                with ExitStack() as uut_exit_stack:
                    try:
                        uut_setup_data = self._callback_registry.uut_setup(
                            system_setup_data=system_setup_data,
                            exit_stack=uut_exit_stack)
                    except QuitTestSystem:  # handle error during uut setup
                        self._quit_requested = True
                        break
                    except Exception as e:
                        logger.exception("caught exception during UUT setup!", exc_info=e)
                        self._error_handler(e)
                        self._is_there_shit_on_the_fan = True
                        break

                    self._raise_accumulated_errors()

                    (
                        sequence_supervision,
                        self._test_step_supervisor
                    ) = TestSequenceSupervision.setup_supervision()

                    try:
                        with sequence_supervision:
                            ret_val = self._callback_registry.test_sequence(
                                system_setup_data=system_setup_data,
                                uut_setup_data=uut_setup_data)
                            sequence_supervision.submit_return_value(ret_val)
                            self._raise_accumulated_errors()
                    except AbortTestSequence:
                        logger.info("terminated test sequence!")
                    except QuitTestSystem:  # handle error during system setup
                        self._quit_requested = True
                        break
                    except Exception as e:
                        logger.exception("caught exception during main sequence!", exc_info=e)
                        self._error_handler(e)
                        self._is_there_shit_on_the_fan = True
                        break
                    finally:
                        self._callback_registry.uut_recovery(
                            system_setup_data=system_setup_data,
                            uut_setup_data=uut_setup_data,
                            test_sequence_data=sequence_supervision.return_value,
                            test_result=sequence_supervision.test_result_info)

                self._callback_registry.uut_result_handler(
                    system_setup_data=system_setup_data,
                    uut_setup_data=uut_setup_data,
                    test_sequence_data=sequence_supervision.return_value,
                    test_result=sequence_supervision.test_result_info)

        except QuitTestSystem:   # handle error during system setup
            self._quit_requested = True
        except Exception as e:
            logger.exception("caught exception during !", exc_info=e)
            self._error_handler(e)
            self._is_there_shit_on_the_fan = True
        finally:
            stack.close()
            logger.info("torn down the test system")
            self.running = False

    def __call__(self):
        self._callback_registry.check()
        self._monitor_thread = Thread(
            target=self.monitor.monitor_loop,
            name="test system monitor"
        )
        self._monitor_thread.start()
        self._test_system_exec_thread = Thread(
            target=self._test_system_exec_loop,
            name="test system execution thread",
        )
        self._test_system_exec_thread.start()

        try:
            while not self._quit_requested and not self._is_there_shit_on_the_fan:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("caught keyboard interrupt! "
                        "Terminating test system execution")
            self._quit_requested = True
            self.running = False

        logger.info("almost done!")
        self.monitor.quit()
        self._monitor_thread.join()
        self._test_system_exec_thread.join(timeout=1)
