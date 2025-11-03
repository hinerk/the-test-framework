from __future__ import annotations

import datetime
import functools
import uuid
from dataclasses import dataclass
from logging import LogRecord
from typing import Callable, Any, Iterator, TYPE_CHECKING


from .helpers import infer_test_result
from ..dtypes import TestStepResultInfo, TestResult


if TYPE_CHECKING:
    from .decorated_test_step import DecoratedTestStep


@dataclass
class TestStepMetadataControl:
    """helper class used to sneak a TestSteps return value and potential
    exception info into its associated TestStepMetadata object

    TestStepMetadata is partially set up before, and finalized after the
    execution of the TestStep. TestStepMetadataControl bundles the required
    methods to complete a TestStepMetadata object after a TestSteps execution
    finished.

    > Why not maintain a PreTestStepMetadata and PostTestStepMetadata?
    TestStepMetadata contains references to a parent (in case the TestStep is
    an embedded one) as well as references to potentially embedded TestStep's
    metadata. Considering this linkage between TestSteps and since those
    TestSteps do not complete simultaneously, there is no obvious point in time
    at which one would translate a "PreTestStepMetadata" tree into a
    "PostTestStepMetadata" one.

    > One might raise the question, whether it would be better(tm) to maintain
    > one single data structure, which combines the functionality of
    > TestStepMetadataControl with the data stored in TestStepMetadata.
    > Ultimately, this is what OOP is all about, right?
    Yes! But TestStepMetadata is allowed to be exposed beyond the scope of the
    framework, while the mechanics to patch the data on TestStep completion is
    inherently private.

    > Why not call TestStepMetadata's private methods directly from the
    > TestStepSupervision object, instead of making this detour via
    > TestStepMetadataControl?
    Accessing private methods on a foreign object is -without doubt - nasty,
    while the nastiness of accessing a private method on an object created
    inside a class method (see: TestStepMetadata.create_controlled_metadata)
    of its own kind is yet to be discussed ;-).
    """
    submit_return_value: Callable[[Any], None]
    submit_exception_info: Callable[[Exception], None]
    submit_log_messages:Callable[[list[LogRecord]], None]
    submit_test_start_time: Callable[[datetime.datetime], None]
    submit_test_end_time: Callable[[datetime.datetime], None]
    complete: Callable[[], None]


class TestStepMetadata:
    """Data Structure for TestStep Metadata"""
    @classmethod
    def create_controlled_metadata(
            cls,
            function: DecoratedTestStep,
            parent: TestStepMetadata | None = None,
    ) -> tuple[TestStepMetadata, TestStepMetadataControl]:
        """creates entangled TestStepMetadata and TestStepMetadataControl pair

        Remark: the sole legitimate instantiation of TestStepMetadata is
                done via TestStepSupervisor.supervise()!

        :param function: the TestStep function call
        :param parent: parent TestStepMetadata
        """
        metadata = cls(function=function, parent=parent)
        control = TestStepMetadataControl(
            submit_return_value=metadata._submit_return_value,
            submit_exception_info=metadata._submit_exception_info,
            submit_log_messages=metadata._submit_log_messages,
            submit_test_start_time=metadata._submit_start_time,
            submit_test_end_time=metadata._submit_end_time,
            complete=metadata._set_completed)
        if parent is not None:
            parent.children.append(metadata)
        return metadata, control

    def __init__(
            self,
            function: DecoratedTestStep,
            parent: TestStepMetadata | None = None,
    ):
        """
        Remark  I: use TestStepMetadata.create_controlled_metadata()
        Remark II: the sole legitimate instantiation of TestStepMetadata is
                   done via TestStepSupervisor.supervise()!

        :param function: the TestStep function
        :param parent: Optional TestStepMetadata of the parent TestStep
        """
        self._call_id = uuid.uuid4()
        self.test_step = function
        self._parent_step = parent

        self._exc_info: Exception | None = None
        self._log_messages: list[LogRecord] | None = None
        self._return_value = None
        self._return_value_is_set = False
        self._test_start_time: datetime.datetime | None = None
        self._test_end_time: datetime.datetime | None = None

        self._embedded_steps: list[TestStepMetadata] = list()

        self._completed = False

    def __repr__(self) -> str:
        name = ">".join([ts.name for ts in [*self.ancestors(), self]])
        return f"<TestStepMetadata {name!r}>"

    def __hash__(self) -> int:
        return hash(self._call_id)

    # *** hidden API used by TestStepMetadataControl **************************

    def _submit_return_value(self, returned: Any):
        """only to be used by TestStepMetadataControl to submit return value"""
        self._return_value = returned
        self._return_value_is_set = True

    def _submit_exception_info(self, exc_info: Exception):
        """only to be used by TestStepMetadataControl to submit exception info"""
        self._exc_info = exc_info

    def _submit_log_messages(self, messages: list[LogRecord]):
        """only to be used by TestStepMetadataControl to submit log messages"""
        self._log_messages = messages

    def _submit_start_time(self, ts: datetime.datetime):
        """only to be used by TestStepMetadataControl to submit test step start time"""
        self._test_start_time = ts

    def _submit_end_time(self, ts: datetime.datetime):
        """only to be used by TestStepMetadataControl to submit test step end time"""
        self._test_end_time = ts

    def _set_completed(self):
        """only to be used by TestStepMetadataControl to set completed"""
        self._completed = True

    # *************************************************************************

    @property
    def name(self) -> str:
        """name of the TestStep"""
        return self.test_step.name

    @property
    def children(self) -> list[TestStepMetadata]:
        """TestStepMetadata of embedded TestSteps"""
        return self._embedded_steps

    @property
    def parent(self) -> TestStepMetadata | None:
        """returns TestStepMetadata of parent test step (or None)"""
        return self._parent_step

    @property
    def completed(self) -> bool:
        """whether TestStep execution was completed"""
        return self._completed

    @property
    def start_time(self) -> datetime.datetime:
        """start time of execution

        :raises RuntimeError: if TestStep has not yet started!
        In doubt, check self.completed before accessing self.start_time.
        """
        if self._test_start_time is None:
            raise RuntimeError("TestStep hasn't been started!")
        return self._test_start_time

    @property
    def end_time(self) -> datetime.datetime:
        """end time of execution

        :raises RuntimeError: if TestStep has not yet finished!
        In doubt, check self.completed before accessing self.end_time.
        """
        if self._test_end_time is None:
            raise RuntimeError("TestStep not yet completed!")
        return self._test_end_time

    @property
    def return_value(self):
        """return value of the TestStep call

        :raises RuntimeError: if return value is not yet submitted.
        In doubt, check self.completed before accessing self.return_value.
        """
        if not self._return_value_is_set:
            raise RuntimeError("return value is not yet set!")
        return self._return_value

    @property
    def exc_info(self) -> Exception | None:
        """info about any exception which might occurred during TestStep execution

        :raises RuntimeError: if TestStep execution is not yet completed.
        In doubt, check self.completed before accessing self.exc_info.
        """
        if not self._completed:
            raise RuntimeError("test step not yet completed!")
        return self._exc_info

    @property
    def log_messages(self) -> list[LogRecord]:
        """a list of LogRecords recorded during the execution of the TestStep

        :raises RuntimeError: if TestStep execution is not yet completed.
        In doubt, check self.completed before accessing self.log_messages.
        """
        if self._log_messages is None:
            raise RuntimeError("Log messages are not yet set!")
        return self._log_messages

    @property
    def test_result(self) -> TestResult:
        """get TestResult for current step

        :raises RuntimeError: if TestStep execution is not yet completed.
        In doubt, check self.completed before accessing self.test_result.
        """
        if not self.completed:
            raise RuntimeError(f"test step {self!r} "
                               f"has not completed yet!")
        inferred_test_result = infer_test_result(self._return_value,
                                                 self._exc_info)
        embedded_results = {t.test_result for t in self._embedded_steps}
        return functools.reduce(
            lambda a, b: a.merge(b), [*embedded_results, inferred_test_result])

    def ancestors(self) -> Iterator[TestStepMetadata]:
        """Iterate this TestSteps Ancestors"""
        if self.parent is not None:
            yield self.parent
            yield from self.parent.ancestors()

    def descendants(self) -> Iterator[TestStepMetadata]:
        """iterate over this TestSteps descendants"""
        for child in self.children:
            yield child
            yield from child.descendants()

    def as_test_step_result_info(self) -> TestStepResultInfo:
        """render Metadata as TestStepResultInfo

        :raises RuntimeError: if TestStep execution is not yet completed.
        In doubt, check self.completed before calling as_test_step_result_info().
        """
        return TestStepResultInfo(
            name=self.name,
            ancestry=self.test_step.ancestry,
            result=self.test_result,
            returned=self.return_value,
            uuid=self._call_id.hex,
            log=self.log_messages,
            embedded_results=[e.as_test_step_result_info() for e in self.children],
            exception=self.exc_info,
        )

    def as_dict(self):
        return dict(
            name=self.name,
            children=[c.as_dict() for c in self.children],
            start_time=self.start_time,
            end_time=self.end_time,
            test_result=self.test_result,
            return_value=self.return_value,
            exc_info=self.exc_info,
            log_messages=self.log_messages,
        )
