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

ACTIVE_US_EAST_1 = {"notificationHubRegion": "us-east-1", "statusSummary": {"reason": "", "status": "ACTIVE"}}
ACTIVE_US_WEST_2 = {"notificationHubRegion": "us-west-2", "statusSummary": {"reason": "", "status": "ACTIVE"}}


def test_absent_reports_unchanged_for_hub_disappearing_during_delete():
    client = Mock()
    client.deregister_notification_hub.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeregisterNotificationHub",
    )
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(plugin, "list_notification_hubs", return_value=[ACTIVE_US_EAST_1, ACTIVE_US_WEST_2]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    client.deregister_notification_hub.assert_called_once_with(notificationHubRegion="us-east-1", aws_retry=True)
    require.assert_called_once_with(
        module,
        client,
        "Notifications",
        {"deregister_notification_hub": ("notificationHubRegion",)},
    )


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["region"]["required"] is True
    assert options["argument_spec"]["region"]["fallback"] == (plugin.env_fallback, ["AWS_REGION", "AWS_DEFAULT_REGION"])


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
        result = plugin.find_notification_hub(plugin.list_notification_hubs(None, module), "us-east-1")

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
        plugin.list_notification_hubs(None, module)

    assert raised.value.values["msg"] == "Unable to list AWS Notifications hubs: AWS returned an invalid hub"


def test_register_rejects_hub_for_different_region():
    client = Mock(register_notification_hub=Mock(return_value={"notificationHubRegion": "us-west-2"}))
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(plugin, "list_notification_hubs", return_value=[]),
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
        patch.object(plugin, "list_notification_hubs", return_value=[]),
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
        patch.object(plugin, "list_notification_hubs", return_value=[inactive]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    client.register_notification_hub.assert_called_once_with(notificationHubRegion="us-east-1")
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
        patch.object(plugin, "list_notification_hubs", return_value=[inactive]),
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
        patch.object(plugin, "list_notification_hubs", return_value=[active]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    client.register_notification_hub.assert_not_called()
    require.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "others",
    [
        [],
        [{"notificationHubRegion": "us-west-2", "statusSummary": {"reason": "", "status": "REGISTERING"}}],
        [{"notificationHubRegion": "us-west-2", "statusSummary": {"reason": "", "status": "INACTIVE"}}],
    ],
)
def test_last_active_hub_is_not_deregistered(others, check_mode):
    client = Mock()
    module = FakeModule({"region": "us-east-1"}, check_mode=check_mode)
    with (
        patch.object(plugin, "list_notification_hubs", return_value=[ACTIVE_US_EAST_1] + others),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert raised.value.values["msg"] == (
        "Unable to delete AWS Notifications hub us-east-1: AWS does not allow deregistering the last ACTIVE hub"
    )
    client.deregister_notification_hub.assert_not_called()
    require.assert_not_called()


def test_active_hub_is_deregistered_when_another_hub_is_active():
    client = Mock()
    module = FakeModule({"region": "us-east-1"})
    with (
        patch.object(plugin, "list_notification_hubs", return_value=[ACTIVE_US_WEST_2, ACTIVE_US_EAST_1]),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    client.deregister_notification_hub.assert_called_once_with(notificationHubRegion="us-east-1", aws_retry=True)


def test_deregister_conflict_is_not_retried():
    module = FakeModule({"region": "us-east-1", "state": "absent"})
    module.client = Mock(return_value=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "ensure_absent"),
    ):
        plugin.main()

    deregister = Mock(
        side_effect=plugin.ClientError(
            {"Error": {"Code": "ConflictException", "Message": "Cannot deregister last ACTIVE notification hub"}},
            "DeregisterNotificationHub",
        )
    )
    with patch("time.sleep") as sleep, pytest.raises(plugin.ClientError):
        module.client.call_args.kwargs["retry_decorator"](deregister)(notificationHubRegion="us-east-1")

    deregister.assert_called_once_with(notificationHubRegion="us-east-1")
    sleep.assert_not_called()


def test_register_retries_conflicts():
    calls = []

    def register(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise plugin.ClientError(
                {"Error": {"Code": "ConflictException", "Message": "deregistering"}},
                "RegisterNotificationHub",
            )

        return {"notificationHubRegion": "us-east-1"}

    client = Mock(register_notification_hub=register)
    with (
        patch.object(plugin, "list_notification_hubs", return_value=[]),
        patch.object(plugin, "require_client_methods"),
        patch("time.sleep"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule({"region": "us-east-1"}))

    assert raised.value.values["changed"]
    assert calls == [{"notificationHubRegion": "us-east-1"}] * 2
