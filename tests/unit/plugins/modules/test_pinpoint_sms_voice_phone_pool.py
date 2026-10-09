from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import pinpoint_sms_voice_phone_pool as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["required_if"] == [
        ("state", "present", ["message_type", "name"]),
        ("state", "absent", ["pool_id"]),
    ]
    assert options["required_one_of"] == [("origination_identity", "pool_id")]


def test_optional_create_parameters_are_not_gated_when_omitted():
    client = Mock()
    module = FakeModule(
        {
            "client_token": None,
            "deletion_protection_enabled": None,
            "iso_country_code": None,
            "message_type": "TRANSACTIONAL",
            "name": "main",
            "origination_identity": "sender-1",
            "pool_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
            "wait_delay": 5,
            "wait_timeout": 300,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    methods = require.call_args.args[3]
    assert methods["describe_pools"] == ("PoolIds", "MaxResults", "NextToken", "Filters", "Owner")
    assert methods["list_pool_origination_identities"] == ("PoolId", "MaxResults", "NextToken")
    assert methods["create_pool"] == (
        "MessageType",
        "OriginationIdentity",
        "Tags",
    )
    assert "tag_resource" not in methods


def test_module_has_no_deletion_protection_default():
    options = assert_module_contract(plugin)
    assert "default" not in options["argument_spec"]["deletion_protection_enabled"]


def test_omitted_deletion_protection_leaves_an_existing_pool_unchanged():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": None,
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "DeletionProtectionEnabled": True,
        "MessageType": "TRANSACTIONAL",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    with (
        patch.object(plugin, "find_pool", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert not raised.value.values["changed"]
    assert raised.value.values["pool"]["deletion_protection_enabled"]
    client.update_pool.assert_not_called()


def test_rejects_lowercase_country_code():
    module = FakeModule({"iso_country_code": "us", "state": "present"})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "uppercase" in raised.value.values["msg"]


def test_name_tag_counts_toward_provider_limit():
    module = FakeModule(
        {
            "iso_country_code": None,
            "name": "main",
            "state": "present",
            "tags": {str(index): "" for index in range(200)},
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "tags must contain at most 200 entries"


def test_existing_pool_rejects_message_type_change():
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "message_type": "TRANSACTIONAL",
            "wait": False,
        }
    )
    with (
        patch.object(
            plugin,
            "find_pool",
            return_value={"MessageType": "PROMOTIONAL", "PoolId": "pool-1"},
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert "Cannot modify message_type" in raised.value.values["msg"]


def test_missing_explicit_pool_id_is_not_replaced_with_an_unselectable_pool():
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "message_type": "TRANSACTIONAL",
            "pool_id": "pool-missing",
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "find_pool", return_value=None),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert "does not exist" in raised.value.values["msg"]


def test_pool_lookup_uses_name_tag_to_disambiguate_sender_pools():
    module = FakeModule(
        {
            "iso_country_code": None,
            "message_type": "TRANSACTIONAL",
            "name": "second",
            "origination_identity": "sender-1",
            "pool_id": None,
        }
    )
    pools = [
        {"PoolId": "pool-1", "Status": "ACTIVE"},
        {"PoolId": "pool-2", "Status": "ACTIVE"},
    ]

    with (
        patch.object(plugin, "describe_pools", return_value=pools),
        patch.object(
            plugin,
            "pool_with_origination_identities",
            side_effect=lambda client, module, pool: dict(
                pool,
                OriginationIdentities=[{"OriginationIdentity": "sender-1"}],
            ),
        ),
        patch.object(
            plugin,
            "pool_with_tags",
            side_effect=[
                dict(pools[0], Tags=[{"Key": "Name", "Value": "first"}]),
                dict(pools[1], Tags=[{"Key": "Name", "Value": "second"}]),
            ],
        ),
    ):
        result = plugin.find_pool(Mock(), module)

    assert result["PoolId"] == "pool-2"


@pytest.mark.parametrize("check_mode", [False, True])
def test_identity_in_a_differently_named_pool_fails_before_create(check_mode):
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": None,
            "iso_country_code": None,
            "message_type": "TRANSACTIONAL",
            "name": "second",
            "origination_identity": "sender-1",
            "pool_id": None,
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        },
        check_mode=check_mode,
    )
    pool = {"MessageType": "TRANSACTIONAL", "PoolId": "pool-1", "Status": "ACTIVE"}

    with (
        patch.object(plugin, "describe_pools", return_value=[pool]),
        patch.object(
            plugin,
            "pool_with_origination_identities",
            return_value=dict(pool, OriginationIdentities=[{"OriginationIdentity": "sender-1"}]),
        ),
        patch.object(
            plugin,
            "pool_with_tags",
            side_effect=lambda client, module, pool: dict(pool, Tags=[{"Key": "Name", "Value": "first"}]),
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert "pool-1" in raised.value.values["msg"]
    assert "pool_id" in raised.value.values["msg"]
    assert not raised.value.values.get("changed")
    client.create_pool.assert_not_called()


def test_identity_in_another_country_pool_does_not_conflict():
    module = FakeModule(
        {
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "name": "second",
            "origination_identity": "sender-1",
            "pool_id": None,
        }
    )
    pool = {"PoolId": "pool-1", "Status": "ACTIVE"}

    with (
        patch.object(plugin, "describe_pools", return_value=[pool]),
        patch.object(
            plugin,
            "pool_with_origination_identities",
            return_value=dict(
                pool,
                OriginationIdentities=[{"IsoCountryCode": "CA", "OriginationIdentity": "sender-1"}],
            ),
        ),
        patch.object(plugin, "pool_with_tags") as pool_with_tags,
    ):
        assert plugin.find_pool(Mock(), module) is None

    pool_with_tags.assert_not_called()


def test_check_mode_projects_new_pool_identity_and_name_tag():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": True,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "origination_identity": "phone-1",
            "purge_tags": True,
            "state": "present",
            "tags": {"Environment": "test"},
            "wait": False,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "find_pool", return_value=None),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    pool = raised.value.values["pool"]
    assert raised.value.values["changed"]
    assert pool["origination_identities"] == [{"iso_country_code": "US", "origination_identity": "phone-1"}]
    assert pool["tags"] == {"Environment": "test", "Name": "primary"}
    client.create_pool.assert_not_called()


def test_check_mode_preserves_existing_empty_pool_identities():
    current = {
        "DeletionProtectionEnabled": False,
        "MessageType": "TRANSACTIONAL",
        "OriginationIdentities": [],
        "PoolArn": "arn:pool",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    module = FakeModule(
        {
            "deletion_protection_enabled": True,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "origination_identity": "phone-1",
            "pool_id": "pool-1",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "find_pool", return_value=current),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(Mock(), module)

    assert raised.value.values["pool"]["origination_identities"] == []


def test_check_mode_does_not_wait_for_existing_pool():
    current = {
        "DeletionProtectionEnabled": False,
        "MessageType": "TRANSACTIONAL",
        "PoolId": "pool-1",
        "Status": "UPDATING",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    module = FakeModule(
        {
            "deletion_protection_enabled": False,
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": True,
        },
        check_mode=True,
    )
    with (
        patch.object(plugin, "find_pool", return_value=current),
        patch.object(plugin, "wait_for_pool_active") as wait_for_active,
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(Mock(), module)

    wait_for_active.assert_not_called()


def test_no_wait_creation_uses_create_result_without_retagging():
    client = Mock()
    client.create_pool.return_value = {
        "PoolArn": "arn:pool",
        "PoolId": "pool-1",
        "Status": "CREATING",
    }
    module = FakeModule(
        {
            "client_token": None,
            "deletion_protection_enabled": False,
            "iso_country_code": "US",
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "origination_identity": "phone-1",
            "purge_tags": True,
            "state": "present",
            "tags": {"Environment": "test"},
            "wait": False,
        }
    )
    with (
        patch.object(plugin, "find_pool", return_value=None),
        patch.object(plugin, "get_pool_by_id") as get_pool_by_id,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["pool"]["tags"] == {"Environment": "test", "Name": "primary"}
    get_pool_by_id.assert_not_called()
    client.tag_resource.assert_not_called()


def test_no_wait_update_waits_for_transition_and_rechecks_state():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": True,
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    transitioning = {
        "DeletionProtectionEnabled": False,
        "MessageType": "TRANSACTIONAL",
        "PoolId": "pool-1",
        "Status": "UPDATING",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    active = dict(
        transitioning,
        DeletionProtectionEnabled=True,
        Status="ACTIVE",
    )
    with (
        patch.object(plugin, "find_pool", return_value=transitioning),
        patch.object(plugin, "wait_for_pool_active", return_value=active) as wait_for_pool_active,
        patch.object(plugin, "pool_with_details", side_effect=lambda client, module, pool: pool),
        patch.object(plugin, "get_pool_by_id") as get_pool_by_id,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_pool_active.assert_called_once_with(client, module, "pool-1")
    get_pool_by_id.assert_not_called()
    client.update_pool.assert_not_called()
    assert not raised.value.values["changed"]


def test_deleting_pool_stops_activation_wait():
    module = FakeModule({"wait_delay": 1, "wait_timeout": 10})
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(
            plugin,
            "describe_pools",
            return_value=[{"PoolId": "pool-1", "Status": "DELETING"}],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_pool_active(Mock(), module, "pool-1")

    assert raised.value.values["status"] == "DELETING"


def test_absent_activation_wait_accepts_external_deletion():
    module = FakeModule({"state": "absent", "wait_delay": 1, "wait_timeout": 10})
    deleting = {"PoolId": "pool-1", "Status": "DELETING"}
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "describe_pools", return_value=[deleting]),
    ):
        result = plugin.wait_for_pool_active(Mock(), module, "pool-1")

    assert result == deleting


def test_absent_activation_wait_accepts_disappearing_pool():
    module = FakeModule({"state": "absent", "wait_delay": 1, "wait_timeout": 10})
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "describe_pools", return_value=[]),
    ):
        result = plugin.wait_for_pool_active(Mock(), module, "pool-1")

    assert result == {}


@pytest.mark.parametrize("waited", [{}, {"PoolId": "pool-1", "Status": "DELETING"}])
def test_absent_stops_when_wait_observes_external_deletion(waited):
    client = Mock()
    module = FakeModule({"pool_id": "pool-1", "state": "absent"})
    with (
        patch.object(
            plugin,
            "describe_pools",
            return_value=[
                {
                    "DeletionProtectionEnabled": True,
                    "PoolId": "pool-1",
                    "Status": "UPDATING",
                }
            ],
        ),
        patch.object(plugin, "wait_for_pool_active", return_value=waited),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "pool" not in raised.value.values
    client.update_pool.assert_not_called()
    client.delete_pool.assert_not_called()


def test_check_mode_absent_treats_deleting_pool_as_absent():
    client = Mock()
    module = FakeModule({"pool_id": "pool-1", "state": "absent"}, check_mode=True)
    with (
        patch.object(
            plugin,
            "describe_pools",
            return_value=[{"PoolId": "pool-1", "Status": "DELETING"}],
        ),
        patch.object(plugin, "wait_for_pool_active") as wait_for_pool_active,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "pool" not in raised.value.values
    wait_for_pool_active.assert_not_called()
    client.update_pool.assert_not_called()
    client.delete_pool.assert_not_called()


def test_absent_tolerates_disappearing_deletion_protection_update():
    client = Mock()
    client.update_pool.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "UpdatePool",
    )
    module = FakeModule({"pool_id": "pool-1", "state": "absent"})
    with (
        patch.object(
            plugin,
            "describe_pools",
            return_value=[
                {
                    "DeletionProtectionEnabled": True,
                    "PoolId": "pool-1",
                    "Status": "ACTIVE",
                }
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    client.delete_pool.assert_not_called()


def test_absent_disables_deletion_protection_before_deleting():
    client = Mock()
    client.update_pool.return_value = {
        "DeletionProtectionEnabled": False,
        "PoolId": "pool-1",
        "Status": "UPDATING",
    }
    client.delete_pool.return_value = {"PoolId": "pool-1", "Status": "DELETING"}
    module = FakeModule({"pool_id": "pool-1", "state": "absent"})

    with (
        patch.object(
            plugin,
            "describe_pools",
            return_value=[
                {
                    "DeletionProtectionEnabled": True,
                    "PoolId": "pool-1",
                    "Status": "ACTIVE",
                }
            ],
        ),
        patch.object(plugin, "wait_for_pool_active") as wait_for_pool_active,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    client.update_pool.assert_called_once_with(
        PoolId="pool-1",
        DeletionProtectionEnabled=False,
        aws_retry=True,
    )
    wait_for_pool_active.assert_called_once_with(client, module, "pool-1", changed=True)
    client.delete_pool.assert_called_once_with(PoolId="pool-1", aws_retry=True)
    assert raised.value.values["changed"]


def test_describe_pools_rejects_malformed_response():
    with (
        patch.object(plugin, "paginated_query_with_retries", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.describe_pools(Mock(), FakeModule({}))

    assert "malformed" in raised.value.values["msg"]


def test_select_pool_by_id_rejects_wrong_pool():
    with pytest.raises(ModuleFail) as raised:
        plugin.select_pool_by_id(
            FakeModule({}),
            [{"PoolId": "pool-2", "Status": "ACTIVE"}],
            "arn:aws:sms-voice:us-east-1:1:pool/pool-1",
        )

    assert "wrong" in raised.value.values["msg"]


def test_absent_does_not_return_stale_data_when_delete_races():
    missing = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeletePool",
    )
    client = Mock()
    client.delete_pool.side_effect = missing
    module = FakeModule({"pool_id": "pool-1", "state": "absent"})
    with (
        patch.object(
            plugin,
            "describe_pools",
            return_value=[{"PoolId": "pool-1", "Status": "ACTIVE"}],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"]
    assert "pool" not in raised.value.values


def test_wait_reuses_the_described_pool_after_update():
    client = Mock()
    client.update_pool.return_value = {
        "DeletionProtectionEnabled": True,
        "MessageType": "TRANSACTIONAL",
        "PoolArn": "arn:pool",
        "PoolId": "pool-1",
        "Status": "UPDATING",
    }
    module = FakeModule(
        {
            "deletion_protection_enabled": True,
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": True,
        }
    )
    current = {
        "DeletionProtectionEnabled": False,
        "MessageType": "TRANSACTIONAL",
        "OriginationIdentities": [],
        "PoolArn": "arn:pool",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    active = dict(client.update_pool.return_value, Status="ACTIVE")
    detailed = dict(active, OriginationIdentities=[], Tags=current["Tags"])
    with (
        patch.object(plugin, "find_pool", return_value=current),
        patch.object(plugin, "wait_for_pool_active", return_value=active) as wait_for_pool_active,
        patch.object(plugin, "pool_with_details", return_value=detailed) as pool_with_details,
        patch.object(plugin, "get_pool_by_id") as get_pool_by_id,
        patch.object(plugin, "reconcile_arn_tags"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_pool_active.assert_called_once_with(client, module, "pool-1", changed=True)
    pool_with_details.assert_called_once_with(client, module, active, changed=True)
    get_pool_by_id.assert_not_called()
    assert raised.value.values["changed"]
    assert raised.value.values["pool"]["deletion_protection_enabled"] is True
    assert raised.value.values["pool"]["status"] == "ACTIVE"


def test_get_pool_by_id_adds_details_to_the_described_pool():
    pool = {"PoolId": "pool-1", "Status": "ACTIVE"}
    with (
        patch.object(plugin, "describe_pools", return_value=[pool]),
        patch.object(plugin, "pool_with_details", return_value="detailed") as pool_with_details,
    ):
        assert plugin.get_pool_by_id("client", "module", "pool-1") == "detailed"

    pool_with_details.assert_called_once_with("client", "module", pool, changed=False)


def test_explicit_pool_id_does_not_require_origination_identity():
    client = Mock()
    module = FakeModule(
        {
            "deletion_protection_enabled": None,
            "iso_country_code": None,
            "message_type": "TRANSACTIONAL",
            "name": "primary",
            "origination_identity": None,
            "pool_id": "pool-1",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
        }
    )
    current = {
        "MessageType": "TRANSACTIONAL",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    with (
        patch.object(plugin, "get_pool_by_id", return_value=current) as get_pool,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    get_pool.assert_called_once_with(client, module, "pool-1")
    assert raised.value.values["changed"] is False
    assert raised.value.values["pool_id"] == "pool-1"
    client.create_pool.assert_not_called()


def active_pool(**overrides):
    pool = {
        "DeletionProtectionEnabled": False,
        "MessageType": "TRANSACTIONAL",
        "OriginationIdentities": [],
        "PoolArn": "arn:pool",
        "PoolId": "pool-1",
        "Status": "ACTIVE",
        "Tags": [{"Key": "Name", "Value": "primary"}],
    }
    pool.update(overrides)
    return pool


def present_params(**overrides):
    params = {
        "deletion_protection_enabled": None,
        "message_type": "TRANSACTIONAL",
        "name": "primary",
        "purge_tags": True,
        "state": "present",
        "tags": {"Env": "test"},
        "wait": False,
        "wait_delay": 1,
        "wait_timeout": 1,
    }
    params.update(overrides)
    return params


@pytest.mark.parametrize(("deletion_protection_enabled", "changed"), [(True, True), (None, False)])
def test_tag_failure_reports_whether_the_pool_was_updated(deletion_protection_enabled, changed):
    client = Mock()
    client.update_pool.return_value = active_pool(DeletionProtectionEnabled=True)
    client.tag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "failed"}}, "TagResource"
    )
    module = FakeModule(present_params(deletion_protection_enabled=deletion_protection_enabled))
    with (
        patch.object(plugin, "find_pool", return_value=active_pool()),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Unable to tag Pinpoint SMS Voice V2 pool arn:pool"
    assert raised.value.values["changed"] is changed
    assert client.update_pool.called is changed


def test_wait_timeout_after_create_reports_changed():
    client = Mock()
    client.create_pool.return_value = active_pool(Status="CREATING")
    module = FakeModule(present_params(origination_identity="+15555550100", iso_country_code="US", wait=True))
    module.params["client_token"] = None
    with (
        patch.object(plugin, "find_pool", return_value=None),
        patch.object(plugin, "describe_pools", return_value=[active_pool(Status="CREATING")]),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"].startswith("Timed out waiting for AWS End User Messaging SMS phone pool pool-1")


def test_wait_timeout_before_any_change_reports_unchanged():
    module = FakeModule(present_params(tags=None, wait=True))
    with (
        patch.object(plugin, "describe_pools", return_value=[active_pool(Status="CREATING")]),
        patch.object(plugin.time, "sleep"),
        patch.object(plugin.time, "monotonic", side_effect=[0, 0, 0, 2]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_pool_active(Mock(), module, "pool-1")

    assert raised.value.values["changed"] is False


def test_delete_failure_after_disabling_deletion_protection_reports_changed():
    client = Mock()
    client.update_pool.return_value = active_pool(DeletionProtectionEnabled=False)
    client.delete_pool.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "failed"}}, "DeletePool"
    )
    module = FakeModule({"pool_id": "pool-1", "state": "absent", "wait_delay": 1, "wait_timeout": 1})
    with (
        patch.object(plugin, "describe_pools", return_value=[active_pool(DeletionProtectionEnabled=True)]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is True


def test_delete_failure_without_earlier_changes_reports_unchanged():
    client = Mock()
    client.delete_pool.side_effect = plugin.ClientError(
        {"Error": {"Code": "InternalServerException", "Message": "failed"}}, "DeletePool"
    )
    module = FakeModule({"pool_id": "pool-1", "state": "absent", "wait_delay": 1, "wait_timeout": 1})
    with (
        patch.object(plugin, "describe_pools", return_value=[active_pool()]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    client.update_pool.assert_not_called()


@pytest.mark.parametrize("changed", [False, True])
def test_pool_tags_report_malformed_tags_with_changed(changed):
    client = Mock()
    client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Name"}]}
    with pytest.raises(ModuleFail) as raised:
        plugin.pool_with_tags(client, FakeModule({}), {"PoolArn": "arn:pool-1"}, changed=changed)

    assert raised.value.values["msg"] == "AWS returned malformed tags for Pinpoint SMS Voice V2 pool arn:pool-1"
    assert raised.value.values["changed"] is changed


def test_pool_id_search_paths_gate_describe_by_pool_ids():
    client = Mock()
    module = FakeModule(
        {
            "client_token": None,
            "deletion_protection_enabled": None,
            "iso_country_code": None,
            "message_type": "TRANSACTIONAL",
            "name": "main",
            "origination_identity": None,
            "pool_id": "pool-1",
            "purge_tags": True,
            "state": "present",
            "tags": None,
            "wait": False,
            "wait_delay": 5,
            "wait_timeout": 300,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    assert require.call_args.args[3]["describe_pools"] == ("PoolIds", "MaxResults", "NextToken")
