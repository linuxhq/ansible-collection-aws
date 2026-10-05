from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import notifications_hub as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    assert_module_contract,
    assert_module_rejects,
)


def test_absent_tolerates_hub_disappearing_during_delete():
    client = Mock()
    client.deregister_notification_hub.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeregisterNotificationHub",
    )
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(plugin, "get_notification_hub", return_value={}),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    require.assert_called_once_with(
        module,
        client,
        "Notifications",
        {"deregister_notification_hub": ("notificationHubRegion",)},
    )


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["region"]["required"] is True


def test_invalid_region_is_rejected():
    assert_module_rejects(
        plugin,
        {"region": "not-a-region", "state": "present"},
        "region must be a valid AWS region name",
    )


@pytest.mark.parametrize("region", ["us-east-1", "us-gov-west-1", "eusc-de-east-1", "ap-southeast-7"])
def test_valid_region_names_are_accepted(region):
    module = FakeModule({"region": region, "state": "present"})
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()


@pytest.mark.parametrize("region", ["abcde-east-1", "us-east", "US-EAST-1", "us-east-1-"])
def test_region_names_outside_the_api_pattern_are_rejected(region):
    assert_module_rejects(
        plugin,
        {"region": region, "state": "present"},
        "region must be a valid AWS region name",
    )


def test_hub_lookup_matches_exact_region():
    hubs = [
        {"notificationHubRegion": "us-west-2", "statusSummary": {"reason": "", "status": "ACTIVE"}},
        {"notificationHubRegion": "us-east-1", "statusSummary": {"reason": "", "status": "ACTIVE"}},
    ]
    module = FakeModule({"region": "us-east-1"})
    with patch.object(plugin, "query_list", return_value=hubs):
        result = plugin.get_notification_hub(None, module)

    assert result == {"notificationHubRegion": "us-east-1", "statusSummary": {"reason": "", "status": "ACTIVE"}}


def test_hub_lookup_rejects_invalid_status():
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(
            plugin,
            "query_list",
            return_value=[{"notificationHubRegion": "us-east-1", "statusSummary": {}}],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.get_notification_hub(None, module)

    assert raised.value.values["msg"] == "Unable to list AWS Notifications hubs: AWS returned an invalid hub"


def test_register_rejects_hub_for_different_region():
    client = Mock(register_notification_hub=Mock(return_value={"notificationHubRegion": "us-west-2"}))
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(plugin, "get_notification_hub", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert (
        raised.value.values["msg"]
        == "Unable to create AWS Notifications hub us-east-1: AWS returned a hub for a different region"
    )
    assert raised.value.values["changed"] is True


def test_invalid_register_response_reports_changed():
    client = Mock(register_notification_hub=Mock(return_value={}))
    with (
        patch.object(plugin, "get_notification_hub", return_value=None),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule({"region": "us-east-1"}))

    assert raised.value.values["changed"] is True


def test_invalid_listed_hub_reports_unchanged():
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_hub(FakeModule({}), {}, "Unable to list AWS Notifications hubs")

    assert raised.value.values["changed"] is False


def test_inactive_hub_is_registered_again():
    client = Mock(register_notification_hub=Mock(return_value={"notificationHubRegion": "us-east-1"}))
    module = FakeModule({"region": "us-east-1"})
    inactive = {
        "notificationHubRegion": "us-east-1",
        "statusSummary": {"status": "INACTIVE"},
    }
    with (
        patch.object(plugin, "get_notification_hub", return_value=inactive),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.register_notification_hub.assert_called_once_with(notificationHubRegion="us-east-1", aws_retry=True)
    require.assert_called_once_with(
        module,
        client,
        "Notifications",
        {"register_notification_hub": ("notificationHubRegion",)},
    )


def test_inactive_hub_is_already_absent():
    client = Mock()
    module = FakeModule({"region": "us-east-1"})
    inactive = {
        "notificationHubRegion": "us-east-1",
        "statusSummary": {"status": "INACTIVE"},
    }
    with (
        patch.object(plugin, "get_notification_hub", return_value=inactive),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert not raised.value.values["changed"]
    client.deregister_notification_hub.assert_not_called()
    require.assert_not_called()


def test_active_hub_does_not_require_register():
    client = Mock()
    module = FakeModule({"region": "us-east-1"})
    active = {
        "notificationHubRegion": "us-east-1",
        "statusSummary": {"status": "ACTIVE"},
    }
    with (
        patch.object(plugin, "get_notification_hub", return_value=active),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    client.register_notification_hub.assert_not_called()
    require.assert_not_called()
