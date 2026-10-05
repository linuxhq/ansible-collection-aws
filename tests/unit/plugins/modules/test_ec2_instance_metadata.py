from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import ec2_instance_metadata as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["required_one_of"] == [
        [
            "http_endpoint",
            "http_put_response_hop_limit",
            "http_tokens",
            "http_tokens_enforced",
            "instance_metadata_tags",
        ]
    ]


def test_rejects_hop_limit_outside_ec2_range():
    module = FakeModule(
        {
            "http_endpoint": None,
            "http_put_response_hop_limit": 65,
            "http_tokens": None,
            "http_tokens_enforced": None,
            "instance_metadata_tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "between 1 and 64" in raised.value.values["msg"]


def test_check_mode_projects_clearing_an_account_default():
    client = Mock()
    module = FakeModule(
        {
            "http_endpoint": None,
            "http_put_response_hop_limit": -1,
            "http_tokens": None,
            "http_tokens_enforced": None,
            "instance_metadata_tags": None,
        },
        check_mode=True,
        client=client,
    )
    current = {
        "http_put_response_hop_limit": 2,
        "http_tokens": "required",
    }
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "get_instance_metadata_defaults", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    assert raised.value.values["account_level"] == {"http_tokens": "required"}
    client.modify_instance_metadata_defaults.assert_not_called()
    assert require.call_count == 1
    assert require.call_args.args[3] == {"get_instance_metadata_defaults": ()}


def test_update_projects_new_defaults_without_a_stale_refresh():
    client = Mock()
    client.modify_instance_metadata_defaults.return_value = {"Return": True}
    module = FakeModule(
        {
            "http_endpoint": None,
            "http_put_response_hop_limit": None,
            "http_tokens": "required",
            "http_tokens_enforced": None,
            "instance_metadata_tags": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "get_instance_metadata_defaults",
            return_value={"http_tokens": "optional"},
        ) as get_defaults,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["account_level"]["http_tokens"] == "required"
    assert get_defaults.call_count == 1
    assert require.call_count == 2
    assert require.call_args.args[3] == {"modify_instance_metadata_defaults": ("HttpTokens",)}


def metadata_params(**overrides):
    params = {
        "http_endpoint": None,
        "http_put_response_hop_limit": None,
        "http_tokens": None,
        "http_tokens_enforced": None,
        "instance_metadata_tags": None,
    }
    params.update(overrides)
    return params


def run_metadata(client, params, current, check_mode=False):
    module = FakeModule(params, check_mode=check_mode, client=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "get_instance_metadata_defaults", return_value=current),
        pytest.raises((ModuleExit, ModuleFail)) as result,
    ):
        plugin.main()

    return result, require


def test_http_tokens_enforced_is_updated():
    client = Mock()
    client.modify_instance_metadata_defaults.return_value = {"Return": True}
    result, require = run_metadata(client, metadata_params(http_tokens_enforced="enabled"), {"managed_by": "account"})

    assert result.type is ModuleExit
    assert result.value.values["account_level"]["http_tokens_enforced"] == "enabled"
    client.modify_instance_metadata_defaults.assert_called_once_with(HttpTokensEnforced="enabled", aws_retry=True)
    assert require.call_args.args[3] == {"modify_instance_metadata_defaults": ("HttpTokensEnforced",)}


@pytest.mark.parametrize("check_mode", [False, True])
def test_declarative_policy_blocks_changes_before_calling_ec2(check_mode):
    client = Mock()
    current = {
        "http_tokens": "optional",
        "managed_by": "declarative-policy",
        "managed_exception_message": "Contact the platform team",
    }
    result, _require = run_metadata(client, metadata_params(http_tokens="required"), current, check_mode=check_mode)

    assert result.type is ModuleFail
    assert "declarative policy" in result.value.values["msg"]
    assert result.value.values["managed_exception_message"] == "Contact the platform team"
    client.modify_instance_metadata_defaults.assert_not_called()


def test_declarative_policy_does_not_block_matching_defaults():
    client = Mock()
    current = {"http_tokens": "required", "managed_by": "declarative-policy"}
    result, _require = run_metadata(client, metadata_params(http_tokens="required"), current)

    assert result.type is ModuleExit
    assert result.value.values["changed"] is False


def test_unconfirmed_modification_fails():
    client = Mock()
    client.modify_instance_metadata_defaults.return_value = {"Return": False}
    result, _require = run_metadata(client, metadata_params(http_tokens="required"), {"http_tokens": "optional"})

    assert result.type is ModuleFail
    assert "did not confirm" in result.value.values["msg"]


def test_unconfirmed_modification_reports_changed():
    client = Mock()
    client.modify_instance_metadata_defaults.return_value = {"Return": False}
    result, _require = run_metadata(client, metadata_params(http_tokens="required"), {"managed_by": "account"})

    assert result.type is ModuleFail
    assert result.value.values["changed"] is True


def test_modification_failure_reports_unchanged():
    client = Mock()
    client.modify_instance_metadata_defaults.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalError", "Message": "failed"}}, "ModifyInstanceMetadataDefaults"
    )
    result, _require = run_metadata(client, metadata_params(http_tokens="required"), {"managed_by": "account"})

    assert result.type is ModuleFail
    assert "changed" not in result.value.values
