# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from pathlib import Path
from unittest.mock import patch

HEADER = [
    "#!/usr/bin/python",
    "# Copyright: Ansible Project",
    "# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)",
]


class ModuleResult(Exception):
    def __init__(self, values):
        super().__init__(values)
        self.values = values


class ModuleExit(ModuleResult):
    pass


class ModuleFail(ModuleResult):
    pass


class ModuleInitialized(Exception):
    pass


class FakeModule:
    def __init__(self, params, check_mode=False, client=None, region="us-east-1"):
        self.check_mode = check_mode
        self.params = params
        self.region = region
        self._client = client

    def client(self, *args, **kwargs):
        return self._client

    def exit_json(self, **values):
        raise ModuleExit(values)

    def fail_json(self, **values):
        raise ModuleFail(values)

    def fail_json_aws(self, exception, **values):
        raise ModuleFail(values)


def assert_module_contract(test, plugin):
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with (
        patch.object(plugin, "AnsibleAWSModule", initialize),
        test.assertRaises(ModuleInitialized),
    ):
        plugin.main()

    test.assertTrue(captured["supports_check_mode"])
    test.assertIsInstance(captured["argument_spec"], dict)
    test.assertEqual(Path(plugin.__file__).read_text().splitlines()[:3], HEADER)
    return captured


def assert_module_rejects(test, plugin, params, message):
    module = FakeModule(params)

    patches = [patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module)]
    if hasattr(plugin, "require_positive_wait_bounds"):
        patches.append(patch.object(plugin, "require_positive_wait_bounds", lambda module, **kwargs: None))

    for item in patches:
        item.start()
        test.addCleanup(item.stop)

    with test.assertRaises(ModuleFail) as raised:
        plugin.main()

    test.assertEqual(raised.exception.values["msg"], message)
