from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import iam_account_alias_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"] == {}


def test_returns_aliases_from_query():
    module = FakeModule({}, client=Mock())
    require_client_methods = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods", require_client_methods),
        patch.object(plugin, "query_list", return_value=["main"]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert require_client_methods.call_args.args[3]["list_account_aliases"] == ("Marker", "MaxItems")
    assert raised.value.values["account_aliases"] == ["main"]


def test_rejects_invalid_aliases():
    module = FakeModule({}, client=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[None]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "Unable to list AWS IAM account aliases: AWS returned an invalid response"
