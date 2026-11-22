# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, WaiterError
from botocore.session import get_session
from botocore.stub import Stubber

from ansible_collections.linuxhq.aws.plugins.module_utils import wait
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


def test_wait_bounds_are_only_required_when_waiting():
    wait.require_positive_wait_bounds(FakeModule({"wait": False}))
    with pytest.raises(ModuleFail):
        wait.require_positive_wait_bounds(FakeModule({"wait": False, "wait_delay": 0, "wait_timeout": 1}), always=True)

    for name in ("wait_delay", "wait_timeout"):
        params = {"wait": True, "wait_delay": 1, "wait_timeout": 1, name: 0}
        with pytest.raises(ModuleFail) as raised:
            wait.require_positive_wait_bounds(FakeModule(params))

        assert raised.value.values["msg"] == f"{name} must be 1 or greater"


@pytest.mark.parametrize(("now", "expected"), [(100, 3), (118.5, 1.5), (121, 0)])
def test_sleep_until_next_poll_never_sleeps_past_the_deadline(now, expected):
    module = FakeModule({"wait_delay": 3})
    with patch.object(wait.time, "monotonic", return_value=now), patch.object(wait.time, "sleep") as sleep:
        wait.sleep_until_next_poll(module, 120)

    sleep.assert_called_once_with(expected)


WAITER_MODEL = {
    "ready": {
        "delay": 1,
        "maxAttempts": 5,
        "operation": "DescribeDocument",
        "acceptors": [
            {"argument": "Document.Status", "expected": "Active", "matcher": "path", "state": "success"},
            {"argument": "Document.Status", "expected": "Failed", "matcher": "path", "state": "failure"},
        ],
    },
}


def stubbed_client(*responses):
    client = get_session().create_client(
        "ssm", region_name="us-east-1", aws_access_key_id="EXAMPLE", aws_secret_access_key="EXAMPLE"
    )
    stubber = Stubber(client)
    for response in responses:
        if isinstance(response, str):
            stubber.add_client_error("describe_document", service_error_code=response)
        else:
            stubber.add_response("describe_document", {"Document": response}, {"Name": "example"})

    stubber.activate()
    return client, stubber


def test_custom_waiter_polls_unmatched_statuses_until_an_acceptor_matches():
    # Botocore keeps polling a response no acceptor matches, so transitional statuses need no retry acceptor.
    client, stubber = stubbed_client({"Status": "Creating"}, {"Status": "Updating"}, {"Status": "Active"})
    with patch("botocore.waiter.time.sleep"):
        wait.custom_waiter(client, WAITER_MODEL, "ready").wait(Name="example")

    stubber.assert_no_pending_responses()


def test_custom_waiter_retries_rate_limit_errors_and_stops_on_failure():
    client, stubber = stubbed_client("Throttling", {"Status": "Failed"})
    with patch("botocore.waiter.time.sleep"), pytest.raises(WaiterError):
        wait.custom_waiter(client, WAITER_MODEL, "ready").wait(Name="example")

    stubber.assert_no_pending_responses()


def test_remaining_wait_timeout_without_a_deadline_is_the_full_budget():
    with patch.object(wait.time, "monotonic") as monotonic:
        assert wait.remaining_wait_timeout(FakeModule({"wait_timeout": 30}), None, "timed out") == 30

    monotonic.assert_not_called()


def test_remaining_wait_timeout_returns_the_whole_seconds_left():
    with patch.object(wait.time, "monotonic", return_value=100.5):
        assert wait.remaining_wait_timeout(FakeModule({"wait_timeout": 30}), 120, "timed out") == 19


@pytest.mark.parametrize("changed", [False, True])
def test_remaining_wait_timeout_fails_once_less_than_a_second_remains(changed):
    with patch.object(wait.time, "monotonic", return_value=119.5), pytest.raises(ModuleFail) as raised:
        wait.remaining_wait_timeout(FakeModule({"wait_timeout": 30}), 120, "timed out", changed=changed)

    assert raised.value.values == {"changed": changed, "msg": "timed out"}


def test_run_waiter_uses_module_delay_and_timeout():
    waiter = Mock()
    module = FakeModule({"wait_delay": 3, "wait_timeout": 30})
    with patch.object(wait, "custom_waiter_config", return_value={"Delay": 3}) as config:
        wait.run_waiter(module, waiter, "failed", Id="id")

    config.assert_called_once_with(30, default_pause=3)
    waiter.wait.assert_called_once_with(Id="id", WaiterConfig={"Delay": 3})


def test_run_waiter_waits_only_for_the_remaining_budget():
    waiter = Mock()
    module = FakeModule({"wait_delay": 3, "wait_timeout": 30})
    with patch.object(wait.time, "monotonic", return_value=100):
        wait.run_waiter(module, waiter, "failed", deadline=112, Id="id")

    assert waiter.wait.call_args.kwargs["WaiterConfig"] == wait.custom_waiter_config(12, default_pause=3)


def test_run_waiter_fails_without_waiting_once_the_budget_is_spent():
    waiter = Mock()
    module = FakeModule({"wait_delay": 3, "wait_timeout": 30})
    with patch.object(wait.time, "monotonic", return_value=112), pytest.raises(ModuleFail) as raised:
        wait.run_waiter(module, waiter, "timed out", changed=True, deadline=112, Id="id")

    assert raised.value.values == {"changed": True, "msg": "timed out"}
    waiter.wait.assert_not_called()


def test_run_waiter_translates_sdk_errors():
    waiter = Mock()
    waiter.wait.side_effect = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "Wait")
    module = FakeModule({"wait_delay": 3, "wait_timeout": 30})
    with pytest.raises(ModuleFail) as raised:
        wait.run_waiter(module, waiter, "timed out")

    assert raised.value.values["msg"] == "timed out"


def test_run_waiter_reports_the_supplied_changed_state():
    waiter = Mock()
    waiter.wait.side_effect = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "Wait")
    module = FakeModule({"wait_delay": 3, "wait_timeout": 30})
    with pytest.raises(ModuleFail) as raised:
        wait.run_waiter(module, waiter, "timed out", changed=True, Id="id")

    assert raised.value.values["changed"] is True
    assert "changed" not in waiter.wait.call_args.kwargs
