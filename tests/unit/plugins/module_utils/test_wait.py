# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from ansible_collections.linuxhq.aws.plugins.module_utils import wait
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
)


class WaitTests(TestCase):
    def test_wait_bounds_are_only_required_when_waiting(self):
        wait.require_positive_wait_bounds(FakeModule({"wait": False}))

        with self.assertRaises(ModuleFail):
            wait.require_positive_wait_bounds(
                FakeModule({"wait": False, "wait_delay": 0, "wait_timeout": 1}),
                always=True,
            )

        for name in ("wait_delay", "wait_timeout"):
            params = {"wait": True, "wait_delay": 1, "wait_timeout": 1, name: 0}
            with self.subTest(name=name), self.assertRaises(ModuleFail) as raised:
                wait.require_positive_wait_bounds(FakeModule(params))
            self.assertEqual(
                raised.exception.values["msg"], f"{name} must be 1 or greater"
            )

    def test_run_waiter_uses_module_delay_and_timeout(self):
        waiter = Mock()
        factory = Mock()
        factory.get_waiter.return_value = waiter
        module = FakeModule({"wait_delay": 3, "wait_timeout": 30})

        with (
            patch.object(wait, "build_waiter_factory", return_value=factory),
            patch.object(
                wait, "custom_waiter_config", return_value={"Delay": 3}
            ) as config,
        ):
            wait.run_waiter(
                module, "client", {"model": True}, "ready", "failed", Id="id"
            )

        factory.get_waiter.assert_called_once_with("client", "ready")
        config.assert_called_once_with(30, default_pause=3)
        waiter.wait.assert_called_once_with(Id="id", WaiterConfig={"Delay": 3})

    def test_run_waiter_translates_sdk_errors(self):
        error = ClientError({"Error": {"Code": "Failed", "Message": "no"}}, "Wait")
        waiter = Mock()
        waiter.wait.side_effect = error
        factory = Mock()
        factory.get_waiter.return_value = waiter
        module = FakeModule({"wait_delay": 3, "wait_timeout": 30})

        with (
            patch.object(wait, "build_waiter_factory", return_value=factory),
            self.assertRaises(ModuleFail) as raised,
        ):
            wait.run_waiter(module, Mock(), {}, "ready", "timed out")

        self.assertEqual(raised.exception.values["msg"], "timed out")
