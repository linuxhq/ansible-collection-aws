# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from botocore.session import get_session

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

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
        self.warnings = []
        self._client = client

    def client(self, *args, **kwargs):
        return self._client

    def warn(self, warning):
        self.warnings.append(warning)

    def exit_json(self, **values):
        raise ModuleExit(values)

    def fail_json(self, **values):
        raise ModuleFail(values)

    def fail_json_aws(self, exception, **values):
        raise ModuleFail(values)


def assert_module_contract(plugin):
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleInitialized

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleInitialized):
        plugin.main()

    assert captured["supports_check_mode"]
    assert isinstance(captured["argument_spec"], dict)
    assert Path(plugin.__file__).read_text().splitlines()[:3] == HEADER
    return captured


def assert_module_rejects(plugin, params, message):
    module = FakeModule(params)
    with ExitStack() as stack:
        stack.enter_context(patch.object(plugin, "AnsibleAWSModule", lambda **kwargs: module))
        if hasattr(plugin, "require_positive_wait_bounds"):
            stack.enter_context(patch.object(plugin, "require_positive_wait_bounds"))

        raised = stack.enter_context(pytest.raises(ModuleFail))
        plugin.main()

    assert raised.value.values["msg"] == message


def documented_returns(plugin):
    return yaml.safe_load(plugin.RETURN)


def assert_documents_shape(contains, service, shape_name):
    """Assert that documented return fields match an SDK structure shape, recursively."""
    shape = get_session().get_service_model(service).shape_for(shape_name)
    _assert_documents_shape(contains, shape, shape_name)


def _assert_documents_shape(contains, shape, path):
    members = {camel_dict_to_snake_dict({name: None}).popitem()[0]: member for name, member in shape.members.items()}
    assert set(members) <= set(contains), f"{path} omits {sorted(set(members) - set(contains))}"
    for name, member in members.items():
        if member.type_name == "structure":
            _assert_documents_shape(contains[name]["contains"], member, f"{path}.{name}")
