from unittest.mock import ANY, Mock, call, patch

import pytest
from botocore.exceptions import WaiterError
from botocore.session import Session
from botocore.stub import Stubber

from ansible_collections.linuxhq.aws.plugins.modules import eks_cluster as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules import utils
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    ModuleExit,
    ModuleFail,
    ModuleInitialized,
    assert_module_contract,
)


class FakeModule(utils.FakeModule):
    """Supply the wait bounds that the argument spec always sets, unless a test overrides them."""

    def __init__(self, params, **kwargs):
        super().__init__(dict({"wait_delay": 15, "wait_timeout": 1200}, **params), **kwargs)


def test_sdk_validation_starts_with_lookup_only():
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "encryption_config": None,
            "name": "example",
            "purge_tags": True,
            "state": "present",
            "tags": {},
            "version": None,
            "wait": False,
            "wait_delay": 15,
            "wait_timeout": 1200,
        }
    )
    module = Mock(params=params, client=Mock(return_value=Mock()))
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "ensure_present"),
    ):
        plugin.main()

    require.assert_called_once_with(
        module,
        module.client.return_value,
        "EKS",
        {"describe_cluster": ("name",)},
    )


def test_sdk_validation_checks_nested_vpc_parameters():
    shape = Mock()
    shape.input_shape.members = {"resourcesVpcConfig": Mock(members={"subnetIds": Mock()})}
    client = Mock()
    client.meta.service_model.operation_model.return_value = shape
    module = Mock()
    plugin.require_nested_request_parameters(
        module,
        client,
        "UpdateClusterConfig",
        {"resourcesVpcConfig": {"endpointPublicAccess": False}},
    )

    assert any(
        "resourcesVpcConfig parameter endpointPublicAccess" in call.kwargs["msg"]
        for call in module.fail_json.call_args_list
    )


def test_tag_limits_are_rejected_before_client_creation():
    module = FakeModule(
        {
            "encryption_config": None,
            "state": "present",
            "tags": {str(index): "" for index in range(51)},
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "tags must contain at most 50 entries"


def test_absent_does_not_validate_unused_create_options():
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "encryption_config": [{}, {}],
            "resources_vpc_config": {"public_access_cidrs": ["not-a-cidr"]},
            "state": "absent",
            "tags": {str(index): "" for index in range(51)},
            "version": None,
        }
    )
    module = FakeModule(params)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_positive_wait_bounds"),
        patch.object(plugin, "ensure_absent") as ensure_absent,
    ):
        plugin.main()

    ensure_absent.assert_called_once_with(None, module)


def test_multiple_encryption_configs_are_rejected():
    module = FakeModule({"encryption_config": [{}, {}], "state": "present"})
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == "encryption_config must contain at most one entry"


def test_absent_tolerates_cluster_disappearing_during_delete():
    client = Mock()
    client.delete_cluster.side_effect = plugin.ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
        "DeleteCluster",
    )
    module = FakeModule({"name": "example", "wait": False})
    with (
        patch.object(
            plugin,
            "describe_cluster",
            return_value={"name": "example", "status": "ACTIVE"},
        ),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "wait_for_cluster_updates") as wait_for_updates,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    wait_for_updates.assert_called_once_with(client, module, deadline=ANY)
    require.assert_called_once_with(module, client, "EKS", {"delete_cluster": ("name",)})
    assert raised.value.values["changed"] is False
    assert raised.value.values["cluster"] == {}


def test_absent_reports_unchanged_when_the_cluster_disappears_before_listing_updates():
    client = Mock()
    module = FakeModule({"name": "example", "wait": True, "wait_delay": 1, "wait_timeout": 60})
    with (
        patch.object(plugin, "describe_cluster", return_value={"name": "example", "status": "ACTIVE"}),
        patch.object(plugin, "require_client_methods"),
        patch.object(
            plugin,
            "paginated_query_with_retries",
            side_effect=plugin.ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
                "ListUpdates",
            ),
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    client.delete_cluster.assert_not_called()
    assert raised.value.values["changed"] is False
    assert raised.value.values["cluster"] == {}


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["wait_timeout"]["default"] == 1200
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


def test_describe_rejects_malformed_response():
    client = Mock(describe_cluster=Mock(return_value={"cluster": None}))
    module = FakeModule({"name": "example"})
    with pytest.raises(ModuleFail) as raised:
        plugin.describe_cluster(client, module)

    assert raised.value.values["msg"] == "EKS returned an invalid cluster"


def test_describe_rejects_malformed_cluster_configuration():
    client = Mock(
        describe_cluster=Mock(
            return_value={
                "cluster": {
                    "arn": "arn:cluster",
                    "name": "example",
                    "resourcesVpcConfig": "invalid",
                    "status": "ACTIVE",
                }
            }
        )
    )
    module = FakeModule({"name": "example"})
    with pytest.raises(ModuleFail) as raised:
        plugin.describe_cluster(client, module)

    assert raised.value.values["msg"] == "EKS returned an invalid cluster"


def test_update_validation_rejects_malformed_response():
    module = FakeModule({"name": "example"})
    with pytest.raises(ModuleFail) as raised:
        plugin.validate_update(module, {"id": "update-1"})

    assert raised.value.values["msg"] == "EKS returned an invalid cluster update"


def test_waited_update_rejects_disappearing_cluster():
    client = Mock(update_cluster_version=Mock(return_value={"update": {"id": "update-1", "status": "InProgress"}}))
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": True,
            "tags": None,
            "version": "1.34",
            "wait": True,
        }
    )
    current = {
        "arn": "arn:cluster",
        "name": "example",
        "status": "ACTIVE",
        "version": "1.33",
    }
    module = FakeModule(params)
    with (
        patch.object(plugin, "describe_cluster", side_effect=[current, None]),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_update"),
        patch.object(plugin, "wait_for_cluster"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "EKS cluster example disappeared after update"


@pytest.mark.parametrize(
    ("method", "updates", "current_version"),
    [
        ("update_cluster_config", {"resources_vpc_config": {"endpoint_public_access": False}}, "1.34"),
        ("update_cluster_version", {}, "1.33"),
    ],
)
def test_update_retries_while_another_update_is_in_progress(method, updates, current_version):
    in_use = plugin.ClientError(
        {"Error": {"Code": "ResourceInUseException", "Message": "update in progress"}},
        "UpdateClusterConfig",
    )
    client = Mock()
    getattr(client, method).side_effect = [in_use, {"update": {"id": "update-1", "status": "InProgress"}}]
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update({"name": "example", "purge_tags": True, "tags": None, "version": "1.34", "wait": False})
    params.update(updates)
    current = {
        "arn": "arn:cluster",
        "name": "example",
        "resourcesVpcConfig": {"endpointPublicAccess": True},
        "status": "ACTIVE",
        "version": current_version,
    }
    module = FakeModule(params)
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        patch.object(plugin, "wait_for_update"),
        patch.object(plugin, "wait_for_cluster"),
        patch("time.sleep"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert getattr(client, method).call_count == 2


def test_changed_request_contains_only_differences():
    current = {"version": "1.32", "resources": {"public": True, "private": False}}
    desired = {"version": "1.32", "resources": {"public": False}}
    assert plugin.changed_request(current, desired) == {"resources": {"public": False}}


def test_changed_ignores_list_order_and_duplicates():
    assert not plugin.changed(
        ["subnet-2", "subnet-1"],
        ["subnet-1", "subnet-2", "subnet-1"],
    )


def test_enabled_log_types_flattens_enabled_entries():
    assert plugin.enabled_log_types(
        {
            "clusterLogging": [
                {"enabled": True, "types": ["api", "audit"]},
                {"enabled": False, "types": ["scheduler"]},
            ]
        }
    ) == {"api", "audit"}


def test_vpc_endpoint_and_network_changes_use_separate_updates():
    client = Mock()
    client.update_cluster_config.side_effect = [
        {"update": {"id": "update-1", "status": "InProgress"}},
        {"update": {"id": "update-2", "status": "InProgress"}},
    ]
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": True,
            "resources_vpc_config": {
                "endpoint_public_access": False,
                "subnet_ids": ["subnet-new-a", "subnet-new-b"],
            },
            "tags": None,
            "wait": False,
        }
    )
    module = FakeModule(params)
    current = {
        "arn": "arn:example",
        "name": "example",
        "resourcesVpcConfig": {
            "endpointPublicAccess": True,
            "subnetIds": ["subnet-old-a", "subnet-old-b"],
        },
        "status": "ACTIVE",
    }
    with (
        patch.object(plugin, "describe_cluster", side_effect=[current, current]),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "require_nested_request_parameters") as nested,
        patch.object(plugin, "wait_for_update") as wait_for_update,
        patch.object(plugin, "wait_for_cluster"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"]
    assert [call.kwargs for call in client.update_cluster_config.call_args_list] == [
        {
            "name": "example",
            "resourcesVpcConfig": {"endpointPublicAccess": False},
        },
        {
            "name": "example",
            "resourcesVpcConfig": {"subnetIds": ["subnet-new-a", "subnet-new-b"]},
        },
    ]
    assert require.call_args_list == [
        call(
            module,
            client,
            "EKS",
            {
                "update_cluster_config": (
                    "resourcesVpcConfig",
                    "name",
                )
            },
        ),
        call(
            module,
            client,
            "EKS",
            {
                "update_cluster_config": (
                    "resourcesVpcConfig",
                    "name",
                )
            },
        ),
        call(module, client, "EKS", {"describe_update": ("name", "updateId")}),
    ]
    assert nested.call_count == 2
    wait_for_update.assert_called_once_with(client, module, "update-1", changed=True, deadline=ANY)
    assert raised.value.values["cluster"]["resources_vpc_config"] == {
        "endpoint_public_access": False,
        "subnet_ids": ["subnet-new-a", "subnet-new-b"],
    }


def test_check_mode_preserves_unmanaged_tags():
    fields = dict.fromkeys(plugin.CREATE_FIELDS)
    fields.update(
        {
            "name": "example",
            "purge_tags": False,
            "tags": {"managed": "new"},
        }
    )
    current = {"name": "example", "tags": {"keep": "yes", "managed": "old"}}

    assert plugin.check_mode_cluster(FakeModule(fields), current)["tags"] == {"keep": "yes", "managed": "new"}


def test_check_mode_purge_keeps_aws_reserved_tags():
    fields = dict.fromkeys(plugin.CREATE_FIELDS)
    fields.update(
        {
            "name": "example",
            "purge_tags": True,
            "tags": {"managed": "new"},
        }
    )
    current = {
        "name": "example",
        "tags": {"aws:cloudformation:stack-name": "stack", "drop": "yes", "managed": "old"},
    }

    assert plugin.check_mode_cluster(FakeModule(fields), current)["tags"] == {
        "aws:cloudformation:stack-name": "stack",
        "managed": "new",
    }
    assert current["tags"] == {"aws:cloudformation:stack-name": "stack", "drop": "yes", "managed": "old"}


def test_additive_tags_reject_a_result_above_the_provider_limit():
    client = Mock()
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": False,
            "tags": {"new": "tag"},
            "wait": False,
        }
    )
    current = {
        "arn": "arn:cluster",
        "name": "example",
        "status": "ACTIVE",
        "tags": {str(index): "" for index in range(50)},
    }
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert raised.value.values["msg"] == "The resulting cluster tags must contain at most 50 entries"
    client.tag_resource.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_tag_limit_ignores_aws_reserved_tags(check_mode):
    client = Mock()
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": False,
            "tags": {"new": "tag"},
            "wait": False,
        }
    )
    reserved = {
        "aws:cloudformation:logical-id": "Cluster",
        "AWS:CloudFormation:stack-id": "arn:stack",
        "aws:cloudformation:stack-name": "stack",
    }
    current = {
        "arn": "arn:cluster",
        "name": "example",
        "status": "ACTIVE",
        "tags": dict(reserved, **{str(index): "" for index in range(49)}),
    }
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values["changed"] is True
    assert raised.value.values["cluster"]["tags"]["new"] == "tag"
    if check_mode:
        client.tag_resource.assert_not_called()
    else:
        client.tag_resource.assert_called_once_with(resourceArn="arn:cluster", tags={"new": "tag"}, aws_retry=True)


def test_tag_limit_still_rejects_more_than_fifty_user_tags_beside_aws_tags():
    client = Mock()
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": False,
            "tags": {"new": "tag"},
            "wait": False,
        }
    )
    current = {
        "arn": "arn:cluster",
        "name": "example",
        "status": "ACTIVE",
        "tags": dict({"aws:cloudformation:stack-name": "stack"}, **{str(index): "" for index in range(50)}),
    }
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=True))

    assert raised.value.values["msg"] == "The resulting cluster tags must contain at most 50 entries"
    client.tag_resource.assert_not_called()


def test_no_wait_change_waits_for_active_cluster_and_rechecks_state():
    client = Mock()
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": True,
            "resources_vpc_config": {"endpoint_public_access": False},
            "tags": None,
            "wait": False,
        }
    )
    transitioning = {
        "arn": "arn:example",
        "name": "example",
        "resourcesVpcConfig": {"endpointPublicAccess": True},
        "status": "UPDATING",
    }
    active = {
        "arn": "arn:example",
        "name": "example",
        "resourcesVpcConfig": {"endpointPublicAccess": False},
        "status": "ACTIVE",
    }
    module = FakeModule(params)
    with (
        patch.object(plugin, "describe_cluster", side_effect=[transitioning, active]),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    wait_for_cluster.assert_called_once_with(client, module, "cluster_active", deadline=ANY)
    client.update_cluster_config.assert_not_called()
    assert not raised.value.values["changed"]


def test_deleting_cluster_waits_then_recreates():
    client = Mock(
        create_cluster=Mock(
            return_value={
                "cluster": {
                    "arn": "arn:cluster",
                    "name": "example",
                    "status": "CREATING",
                }
            }
        )
    )
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        {
            "name": "example",
            "purge_tags": True,
            "resources_vpc_config": {"subnet_ids": ["subnet-1", "subnet-2"]},
            "role_arn": "arn:role",
            "tags": None,
            "wait": False,
        }
    )
    module = FakeModule(params)
    with (
        patch.object(
            plugin,
            "describe_cluster",
            side_effect=[{"name": "example", "status": "DELETING"}, None],
        ),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    wait_for_cluster.assert_called_once_with(client, module, "cluster_deleted", deadline=ANY)
    assert require.call_args.args[3] == {
        "create_cluster": (
            "resourcesVpcConfig",
            "roleArn",
            "name",
        )
    }
    client.create_cluster.assert_called_once()


def test_absent_does_not_repeat_an_in_progress_delete():
    client = Mock()
    module = FakeModule({"name": "example", "wait": False})
    with (
        patch.object(
            plugin,
            "describe_cluster",
            return_value={"name": "example", "status": "DELETING"},
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert not raised.value.values["changed"]
    client.delete_cluster.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("status", ["ACTIVE", "UPDATING"])
def test_absent_fails_without_waiting_when_deletion_protection_is_enabled(check_mode, status):
    client = Mock()
    module = FakeModule({"name": "example", "wait": True}, check_mode=check_mode)
    with (
        patch.object(
            plugin,
            "describe_cluster",
            return_value={"name": "example", "status": status, "deletionProtection": True},
        ),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        patch.object(plugin, "wait_for_cluster_updates") as wait_for_updates,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_absent(client, module)

    assert raised.value.values["changed"] is False
    assert "example" in raised.value.values["msg"]
    assert "deletion_protection=false" in raised.value.values["msg"]
    wait_for_cluster.assert_not_called()
    wait_for_updates.assert_not_called()
    client.delete_cluster.assert_not_called()
    client.update_cluster_config.assert_not_called()


def test_new_cluster_requires_role_and_subnets():
    base = dict.fromkeys(plugin.CREATE_FIELDS)
    base.update({"name": "example", "tags": None, "wait": False})
    cases = [
        (
            dict(
                base,
                resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
                role_arn=None,
            ),
            "role_arn is required",
        ),
        (
            dict(base, resources_vpc_config=None, role_arn="arn:role"),
            "resources_vpc_config.subnet_ids is required",
        ),
    ]
    for params, message in cases:
        with (
            patch.object(plugin, "describe_cluster", return_value=None),
            pytest.raises(ModuleFail) as raised,
        ):
            plugin.ensure_present(Mock(), FakeModule(params))

        assert message in raised.value.values["msg"]


def test_failed_update_stops_waiting_with_update_details():
    client = Mock(describe_update=Mock(return_value={"update": {"id": "update-1", "status": "Failed"}}))
    module = FakeModule({"name": "example", "wait_delay": 1, "wait_timeout": 10})
    with (
        patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
        patch.object(plugin, "require_client_methods") as require,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_update(client, module, "update-1")

    # ensure_present checks describe_update support before the first update.
    require.assert_not_called()
    assert raised.value.values["update"]["status"] == "Failed"


def test_cluster_waiter_uses_requested_delay():
    waiter = Mock()
    client = Mock(get_waiter=Mock(return_value=waiter))
    module = FakeModule({"name": "example", "wait_delay": 7, "wait_timeout": 20})
    plugin.wait_for_cluster(client, module, "cluster_active")

    client.get_waiter.assert_called_once_with("cluster_active")
    waiter.wait.assert_called_once_with(
        name="example",
        WaiterConfig={"Delay": 7, "MaxAttempts": 3},
    )


@pytest.mark.parametrize(
    ("waiter_name", "state"),
    [("cluster_active", "active"), ("cluster_deleted", "deleted")],
)
def test_cluster_waiter_failure_names_the_target_state(waiter_name, state):
    waiter = Mock()
    waiter.wait.side_effect = WaiterError(waiter_name, "terminal failure state", {})
    module = FakeModule({"name": "example", "wait_delay": 5, "wait_timeout": 10})
    with pytest.raises(ModuleFail) as raised:
        plugin.wait_for_cluster(Mock(get_waiter=Mock(return_value=waiter)), module, waiter_name)

    assert raised.value.values["msg"] == f"Unable to wait for AWS EKS cluster example to become {state}"


def eks_params(**overrides):
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(name="example", tags=None, purge_tags=True, wait=False)
    params.update(overrides)
    return params


@pytest.mark.parametrize("enabled", [True, False])
def test_eks_auto_mode_settings_use_one_request(enabled):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "computeConfig": {"enabled": not enabled},
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": not enabled}},
        "storageConfig": {"blockStorage": {"enabled": not enabled}},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            compute_config={"enabled": enabled},
            kubernetes_network_config={"ip_family": "ipv4", "elastic_load_balancing": {"enabled": enabled}},
            storage_config={"block_storage": {"enabled": enabled}},
        )
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        patch.object(plugin, "wait_for_update"),
        patch.object(plugin, "wait_for_cluster"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_called_once_with(
        name="example",
        computeConfig={"enabled": enabled},
        kubernetesNetworkConfig={"elasticLoadBalancing": {"enabled": enabled}},
        storageConfig={"blockStorage": {"enabled": enabled}},
    )


@pytest.mark.parametrize(
    "log_type, enabled, expected_changed",
    [
        ("api", False, False),
        ("audit", True, False),
        ("api", True, True),
        ("audit", False, True),
    ],
)
def test_eks_partial_logging_is_idempotent(log_type, enabled, expected_changed):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "logging": {
            "clusterLogging": [
                {"types": ["audit"], "enabled": True},
                {"types": ["api", "authenticator", "controllerManager", "scheduler"], "enabled": False},
            ]
        },
    }
    module = FakeModule(
        eks_params(logging={"cluster_logging": [{"types": [log_type], "enabled": enabled}]}), check_mode=True
    )
    with patch.object(plugin, "describe_cluster", return_value=current), pytest.raises(ModuleExit) as result:
        plugin.ensure_present(Mock(), module)

    assert result.value.values["changed"] is expected_changed


def test_eks_result_preserves_tag_keys():
    module = FakeModule({"name": "example"})
    with pytest.raises(ModuleExit) as result:
        plugin.exit_result(module, False, {"tags": {"CostCenter": "engineering", "cost_center": "other"}}, "present")

    assert result.value.values["cluster"]["tags"] == {"CostCenter": "engineering", "cost_center": "other"}


def test_eks_creation_preserves_distinct_tag_keys():
    tags = {"cost_center": "finance", "costCenter": "engineering"}
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(
        name="review",
        role_arn="arn:aws:iam::123456789012:role/review",
        resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
        tags=tags,
        wait=False,
        purge_tags=True,
    )
    client = Mock()
    client.create_cluster.return_value = {
        "cluster": {"arn": "arn:aws:eks:us-east-1:123456789012:cluster/review", "name": "review", "status": "CREATING"}
    }
    with (
        patch.object(plugin, "describe_cluster", return_value=None),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, FakeModule(params))

    assert client.create_cluster.call_args.kwargs["tags"] == tags


@pytest.mark.parametrize("status", ["CREATING", "UPDATING"])
@pytest.mark.parametrize("tags", [None, {"Environment": "test"}])
def test_check_mode_predicts_changes_without_waiting_for_active_cluster(status, tags):
    params = dict.fromkeys(plugin.CREATE_FIELDS)
    params.update(name="example", tags=tags, version=None, wait=True, purge_tags=True, wait_timeout=1200, wait_delay=15)
    module = FakeModule(params, check_mode=True)
    client = Mock()
    current = {"name": "example", "arn": "arn:aws:eks:us-east-1:123456789012:cluster/example", "status": status}
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "wait_for_cluster") as waiter,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    waiter.assert_not_called()
    assert result.value.values["changed"] is (tags is not None)
    # With wait=true the real run waits for the cluster to become ACTIVE.
    assert result.value.values["cluster"]["status"] == "ACTIVE"
    assert current["status"] == status
    if tags is not None:
        assert result.value.values["cluster"]["tags"] == tags

    client.update_cluster_config.assert_not_called()
    client.tag_resource.assert_not_called()


def run_present(module, described, client=None):
    """Run ensure_present with describe results and waits mocked; return the client and the result."""
    client = client or Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    client.update_cluster_version.return_value = {"update": {"id": "update-2", "status": "InProgress"}}
    with (
        patch.object(plugin, "describe_cluster", side_effect=described),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        patch.object(plugin, "wait_for_cluster"),
        patch.object(plugin, "wait_for_update"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    return client, raised.value.values


# The CreateCluster response and the ACTIVE DescribeCluster body for an untagged cluster, trimmed (live probe).
CREATED_CLUSTER = {
    "arn": "arn:example",
    "name": "example",
    "status": "CREATING",
    "roleArn": "arn:role",
    "resourcesVpcConfig": {"subnetIds": ["subnet-1", "subnet-2"]},
    "accessConfig": {"authenticationMode": "API", "bootstrapClusterCreatorAdminPermissions": True},
    "tags": {},
}
DESCRIBED_CLUSTER = dict(CREATED_CLUSTER, status="ACTIVE", accessConfig={"authenticationMode": "API"})


@pytest.mark.parametrize("wait", [True, False])
def test_check_mode_create_predicts_the_status_tags_and_access_config_a_real_create_returns(wait):
    params = eks_params(
        access_config={"authentication_mode": "API", "bootstrap_cluster_creator_admin_permissions": True},
        resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
        role_arn="arn:role",
        wait=wait,
    )
    client = Mock(create_cluster=Mock(return_value={"cluster": CREATED_CLUSTER}))
    client, real = run_present(FakeModule(params), [None, DESCRIBED_CLUSTER], client)
    check_client, check = run_present(FakeModule(params, check_mode=True), [None])

    assert check_client.mock_calls == []
    assert check["changed"] is real["changed"] is True
    predicted = {key: check["cluster"][key] for key in ("access_config", "status", "tags")}
    assert predicted == {key: real["cluster"][key] for key in predicted}
    assert predicted["status"] == ("ACTIVE" if wait else "CREATING")
    assert predicted["tags"] == {}


@pytest.mark.parametrize("wait", [True, False])
def test_check_mode_create_predicts_supplied_tags(wait):
    params = eks_params(
        resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
        role_arn="arn:role",
        tags={"Env": "prod"},
        wait=wait,
    )

    check = run_present(FakeModule(params, check_mode=True), [None])[1]

    assert check["cluster"]["tags"] == {"Env": "prod"}


@pytest.mark.parametrize("wait", [True, False])
@pytest.mark.parametrize("status", ["CREATING", "PENDING", "UPDATING"])
def test_check_mode_predicts_the_active_status_a_real_change_waits_for(status, wait):
    params = eks_params(tags={"Env": "prod"}, wait=wait)
    transitioning = dict(DESCRIBED_CLUSTER, status=status)

    real = run_present(FakeModule(params), [transitioning, DESCRIBED_CLUSTER, DESCRIBED_CLUSTER])[1]
    check_client, check = run_present(FakeModule(params, check_mode=True), [transitioning])

    assert check_client.mock_calls == []
    assert check == real
    assert check["cluster"]["status"] == "ACTIVE"


@pytest.mark.parametrize("status", ["CREATING", "PENDING", "UPDATING"])
def test_check_mode_keeps_a_transitional_status_when_nothing_waits(status):
    transitioning = dict(DESCRIBED_CLUSTER, status=status)
    params = eks_params(wait=False)

    real = run_present(FakeModule(params), [transitioning])[1]
    check = run_present(FakeModule(params, check_mode=True), [transitioning])[1]

    assert check == real
    assert check["changed"] is False
    assert check["cluster"]["status"] == status


# Settings that compare equal to an untagged standard cluster but are spelled differently from what EKS returns.
EQUAL_SETTINGS = {
    "compute_config": {"enabled": False, "node_pools": []},
    "remote_network_config": {"remote_node_networks": [], "remote_pod_networks": []},
    "resources_vpc_config": {"subnet_ids": ["subnet-b", "subnet-a"]},
    "zonal_shift_config": {"enabled": False},
}
STANDARD_CLUSTER = dict(
    DESCRIBED_CLUSTER,
    kubernetesNetworkConfig={"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": False}},
    resourcesVpcConfig={"endpointPublicAccess": True, "subnetIds": ["subnet-a", "subnet-b"]},
)


def test_check_mode_tag_change_keeps_the_settings_eks_stores():
    params = eks_params(tags={"Env": "prod"}, wait=True, **EQUAL_SETTINGS)

    real_client, real = run_present(FakeModule(params), [STANDARD_CLUSTER])
    check_client, check = run_present(FakeModule(params, check_mode=True), [STANDARD_CLUSTER])

    real_client.update_cluster_config.assert_not_called()
    real_client.tag_resource.assert_called_once()
    assert check_client.mock_calls == []
    assert check == real
    assert check["cluster"]["resources_vpc_config"]["subnet_ids"] == ["subnet-a", "subnet-b"]
    assert not {"compute_config", "remote_network_config", "zonal_shift_config"} & set(check["cluster"])


def test_unwaited_change_overlays_only_the_settings_it_sends():
    settings = dict(EQUAL_SETTINGS)
    settings["resources_vpc_config"] = {"endpoint_public_access": False, "subnet_ids": ["subnet-b", "subnet-a"]}
    params = eks_params(tags={"Env": "prod"}, version="1.35", wait=False, **settings)
    current = dict(STANDARD_CLUSTER, version="1.34")

    real_client, real = run_present(FakeModule(params), [current])
    check_client, check = run_present(FakeModule(params, check_mode=True), [current])

    assert real_client.update_cluster_config.call_args_list == [
        call(name="example", resourcesVpcConfig={"endpointPublicAccess": False})
    ]
    real_client.update_cluster_version.assert_called_once_with(name="example", version="1.35")
    assert check_client.mock_calls == []
    assert check == real
    assert check["cluster"]["version"] == "1.35"
    assert check["cluster"]["resources_vpc_config"] == {
        "endpoint_public_access": False,
        "subnet_ids": ["subnet-a", "subnet-b"],
    }
    assert not {"compute_config", "remote_network_config", "zonal_shift_config"} & set(check["cluster"])


@pytest.mark.parametrize("wait", [True, False])
def test_check_mode_create_result_omits_only_keys_documented_as_conditional(wait):
    params = eks_params(resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]}, role_arn="arn:role", wait=wait)
    check = run_present(FakeModule(params, check_mode=True), [None])[1]
    cluster_returns = utils.documented_returns(plugin)["cluster"]["contains"]

    def assert_documented(contains, result, path):
        for key, documented in contains.items():
            if key not in result:
                assert documented["returned"] != "always", f"{path}{key}"
                assert "when the cluster exists" != documented["returned"], f"{path}{key}"
                assert "when the cluster is active" != documented["returned"], f"{path}{key}"
            elif "contains" in documented:
                assert_documented(documented["contains"], result[key], f"{path}{key}.")

    assert_documented(cluster_returns, check["cluster"], "")


@pytest.mark.parametrize("check_mode", [False, True])
def test_partial_update_result_preserves_unmanaged_configuration(check_mode):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "accessConfig": {"authenticationMode": "API", "bootstrapClusterCreatorAdminPermissions": False},
        "resourcesVpcConfig": {
            "endpointPublicAccess": True,
            "endpointPrivateAccess": True,
            "subnetIds": ["subnet-1", "subnet-2"],
        },
    }
    module = FakeModule(
        eks_params(
            resources_vpc_config={"endpoint_public_access": False},
            access_config={"authentication_mode": "API", "bootstrap_cluster_creator_admin_permissions": True},
            bootstrap_self_managed_addons=True,
        ),
        check_mode=check_mode,
    )
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["cluster"]["resources_vpc_config"] == {
        "endpoint_public_access": False,
        "endpoint_private_access": True,
        "subnet_ids": ["subnet-1", "subnet-2"],
    }
    assert current["resourcesVpcConfig"]["endpointPublicAccess"] is True
    assert result.value.values["cluster"]["access_config"]["bootstrap_cluster_creator_admin_permissions"] is False
    assert "bootstrap_self_managed_addons" not in result.value.values["cluster"]
    if check_mode:
        client.update_cluster_config.assert_not_called()
    else:
        client.update_cluster_config.assert_called_once_with(
            name="example", resourcesVpcConfig={"endpointPublicAccess": False}
        )


@pytest.mark.parametrize("check_mode", [False, True])
def test_partial_logging_result_preserves_unmanaged_log_types(check_mode):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "logging": {"clusterLogging": [{"types": ["api", "audit"], "enabled": True}]},
    }
    module = FakeModule(
        eks_params(logging={"cluster_logging": [{"types": ["api"], "enabled": False}]}),
        check_mode=check_mode,
    )
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    entries = result.value.values["cluster"]["logging"]["cluster_logging"]
    assert {log_type: entry["enabled"] for entry in entries for log_type in entry["types"]} == {
        "api": False,
        "audit": True,
    }
    assert current["logging"]["clusterLogging"] == [{"types": ["api", "audit"], "enabled": True}]


def test_access_and_upgrade_settings_have_no_module_defaults():
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        raise ModuleExit({})

    with patch.object(plugin, "AnsibleAWSModule", initialize), pytest.raises(ModuleExit):
        plugin.main()

    spec = captured["argument_spec"]
    assert "default" not in spec["access_config"]
    assert "default" not in spec["access_config"]["options"]["authentication_mode"]
    assert "default" not in spec["upgrade_policy"]
    assert "default" not in spec["upgrade_policy"]["options"]["support_type"]


def test_omitted_access_and_upgrade_settings_leave_the_cluster_unchanged():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "accessConfig": {"authenticationMode": "CONFIG_MAP"},
        "upgradePolicy": {"supportType": "STANDARD"},
        "deletionProtection": False,
    }
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, FakeModule(eks_params()))

    assert result.value.values["changed"] is False
    assert client.mock_calls == []


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"deletion_protection": True}, {"deletionProtection": True}),
        (
            {"remote_network_config": {"remote_node_networks": [{"cidrs": ["10.80.0.0/16"]}]}},
            {"remoteNetworkConfig": {"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16"]}]}},
        ),
    ],
)
def test_deletion_protection_and_remote_networks_use_their_own_update(overrides, expected):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "deletionProtection": False,
        "remoteNetworkConfig": {
            "remoteNodeNetworks": [{"cidrs": ["10.90.0.0/16"]}],
            "remotePodNetworks": [{"cidrs": ["10.91.0.0/16"]}],
        },
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods") as require_methods,
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, FakeModule(eks_params(**overrides)))

    assert result.value.values["changed"] is True
    client.update_cluster_config.assert_called_once_with(name="example", **expected)
    assert require_methods.call_args.args[3] == {"update_cluster_config": tuple(expected) + ("name",)}


def test_matching_remote_networks_are_unchanged():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "remoteNetworkConfig": {"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16", "10.81.0.0/16"]}]},
    }
    client = Mock()
    module = FakeModule(
        eks_params(remote_network_config={"remote_node_networks": [{"cidrs": ["10.81.0.0/16", "10.80.0.0/16"]}]})
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_present(client, module)

    assert result.value.values["changed"] is False
    assert client.mock_calls == []


def test_remote_networks_accept_at_most_one_entry():
    module = FakeModule(
        eks_params(
            encryption_config=None,
            remote_network_config={"remote_pod_networks": [{"cidrs": ["10.80.0.0/16"]}, {"cidrs": ["10.81.0.0/16"]}]},
            state="present",
            wait_delay=15,
            wait_timeout=60,
        )
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as result,
    ):
        plugin.main()

    assert result.value.values["msg"] == "remote_network_config.remote_pod_networks must contain at most one entry"


def test_delete_waits_for_in_progress_cluster_updates_first():
    client = Mock()
    module = FakeModule({"name": "example", "wait": False, "wait_delay": 1, "wait_timeout": 60})
    calls = []
    client.delete_cluster.side_effect = lambda **kwargs: calls.append("delete")
    client.describe_update.side_effect = [
        {"update": {"id": "old", "status": "Failed"}},
        {"update": {"id": "auto", "status": "InProgress"}},
        {"update": {"id": "auto", "status": "Successful"}},
    ]
    with (
        patch.object(plugin, "describe_cluster", return_value={"name": "example", "status": "ACTIVE"}),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"updateIds": ["old", "auto"]}) as query,
        patch.object(plugin.time, "sleep"),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.ensure_absent(client, module)

    assert result.value.values["changed"] is True
    query.assert_called_once_with(client, "list_updates", name="example")
    assert client.describe_update.call_count == 3
    assert calls == ["delete"]


def test_failed_update_still_fails_a_requested_change():
    client = Mock()
    client.describe_update.return_value = {"update": {"id": "update-1", "status": "Failed"}}
    module = FakeModule({"name": "example", "wait_delay": 1, "wait_timeout": 60})
    with patch.object(plugin, "require_client_methods"), pytest.raises(ModuleFail):
        plugin.wait_for_update(client, module, "update-1")


def eks_client():
    return Session().create_client(
        "eks",
        region_name="us-east-1",
        aws_access_key_id="EXAMPLE",
        aws_secret_access_key="EXAMPLE",
    )


@pytest.mark.parametrize(
    ("waiter_name", "status", "state"),
    [
        ("cluster_active", "FAILED", "active"),
        ("cluster_active", "DELETING", "active"),
        ("cluster_deleted", "ACTIVE", "deleted"),
    ],
)
def test_cluster_waiter_stops_on_a_terminal_state(waiter_name, status, state):
    client = eks_client()
    module = FakeModule({"name": "example", "wait_delay": 15, "wait_timeout": 1200})
    with Stubber(client) as stubber, pytest.raises(ModuleFail) as raised:
        stubber.add_response(
            "describe_cluster", {"cluster": {"name": "example", "status": status}}, {"name": "example"}
        )
        plugin.wait_for_cluster(client, module, waiter_name)

    stubber.assert_no_pending_responses()
    assert raised.value.values["msg"] == f"Unable to wait for AWS EKS cluster example to become {state}"


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    ("field", "value"),
    [("ip_family", "ipv6"), ("service_ipv4_cidr", "172.20.0.0/16")],
)
def test_create_only_network_settings_fail_before_any_update(field, value, check_mode):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "serviceIpv4Cidr": "10.100.0.0/16"},
        "deletionProtection": False,
    }
    client = Mock()
    module = FakeModule(
        eks_params(deletion_protection=True, kubernetes_network_config={field: value}),
        check_mode=check_mode,
    )
    with patch.object(plugin, "describe_cluster", return_value=current), pytest.raises(ModuleFail) as raised:
        plugin.ensure_present(client, module)

    assert (
        raised.value.values["msg"]
        == f"Cannot modify kubernetes_network_config.{field} for existing EKS cluster example"
    )
    client.update_cluster_config.assert_not_called()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"role_arn": "arn:aws:iam::123456789012:role/example"}, None),
        ({"role_arn": "arn:aws:iam::123456789012:role/other"}, "Cannot modify role_arn"),
        (
            {"encryption_config": [{"provider": {"key_arn": "arn:key"}, "resources": ["secrets", "configmaps"]}]},
            None,
        ),
        (
            {"encryption_config": [{"provider": {"key_arn": "arn:other"}, "resources": ["configmaps", "secrets"]}]},
            "Cannot modify encryption_config",
        ),
    ],
)
def test_create_only_settings_compare_the_current_value(overrides, message):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "roleArn": "arn:aws:iam::123456789012:role/example",
        "encryptionConfig": [{"provider": {"keyArn": "arn:key"}, "resources": ["configmaps", "secrets"]}],
    }
    client = Mock()
    module = FakeModule(eks_params(**overrides))
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleFail if message else ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    if message:
        assert raised.value.values["msg"] == f"{message} for existing EKS cluster example"
    else:
        assert raised.value.values["changed"] is False

    assert client.mock_calls == []


def test_auto_mode_load_balancing_updates_with_matching_create_only_network_settings():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "computeConfig": {"enabled": True, "nodePools": ["general-purpose", "system"], "nodeRoleArn": "arn:node"},
        "kubernetesNetworkConfig": {
            "ipFamily": "ipv4",
            "serviceIpv4Cidr": "10.100.0.0/16",
            "elasticLoadBalancing": {"enabled": False},
        },
        "storageConfig": {"blockStorage": {"enabled": True}},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            kubernetes_network_config={
                "ip_family": "ipv4",
                "service_ipv4_cidr": "10.100.0.0/16",
                "elastic_load_balancing": {"enabled": True},
            },
        )
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_called_once_with(
        name="example",
        computeConfig={"enabled": True, "nodePools": ["general-purpose", "system"], "nodeRoleArn": "arn:node"},
        kubernetesNetworkConfig={"elasticLoadBalancing": {"enabled": True}},
        storageConfig={"blockStorage": {"enabled": True}},
    )


def test_auto_mode_node_pool_change_sends_every_capability_together():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "computeConfig": {"enabled": True, "nodePools": ["system"], "nodeRoleArn": "arn:node"},
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": True}},
        "storageConfig": {"blockStorage": {"enabled": True}},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            compute_config={"enabled": True, "node_pools": ["general-purpose", "system"], "node_role_arn": "arn:node"},
            kubernetes_network_config={"elastic_load_balancing": {"enabled": True}},
            storage_config={"block_storage": {"enabled": True}},
        )
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    client.update_cluster_config.assert_called_once_with(
        name="example",
        computeConfig={"enabled": True, "nodePools": ["general-purpose", "system"], "nodeRoleArn": "arn:node"},
        kubernetesNetworkConfig={"elasticLoadBalancing": {"enabled": True}},
        storageConfig={"blockStorage": {"enabled": True}},
    )


def test_auto_mode_request_fills_omitted_enabled_flags_from_the_cluster():
    current = {
        "computeConfig": {"enabled": True, "nodePools": ["system"], "nodeRoleArn": "arn:node"},
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": True}},
        "storageConfig": {"blockStorage": {"enabled": True}},
    }

    assert plugin.auto_mode_request(current, {"computeConfig": {"nodePools": ["general-purpose"]}}) == {
        "computeConfig": {"enabled": True, "nodePools": ["general-purpose"], "nodeRoleArn": "arn:node"},
        "kubernetesNetworkConfig": {"elasticLoadBalancing": {"enabled": True}},
        "storageConfig": {"blockStorage": {"enabled": True}},
    }


@pytest.mark.parametrize(
    ("compute_config", "expected"),
    [
        ({"nodePools": []}, {"enabled": True, "nodePools": [], "nodeRoleArn": "arn:node"}),
        (
            {"nodePools": ["general-purpose"], "nodeRoleArn": "arn:other"},
            {"enabled": True, "nodePools": ["general-purpose"], "nodeRoleArn": "arn:other"},
        ),
        ({"enabled": False}, {"enabled": False}),
    ],
)
def test_auto_mode_request_keeps_supplied_compute_settings(compute_config, expected):
    current = {
        "computeConfig": {"enabled": True, "nodePools": ["general-purpose", "system"], "nodeRoleArn": "arn:node"},
    }

    assert plugin.auto_mode_request(current, {"computeConfig": compute_config})["computeConfig"] == expected


def test_auto_mode_request_never_sends_create_only_network_settings():
    request = plugin.auto_mode_request(
        {"kubernetesNetworkConfig": {"ipFamily": "ipv4", "serviceIpv4Cidr": "10.100.0.0/16"}},
        {
            "kubernetesNetworkConfig": {
                "elasticLoadBalancing": {"enabled": False},
                "ipFamily": "ipv4",
                "serviceIpv4Cidr": "10.100.0.0/16",
            }
        },
    )

    assert request == {"kubernetesNetworkConfig": {"elasticLoadBalancing": {"enabled": False}}}


@pytest.mark.parametrize("status", ["CREATING", "UPDATING"])
def test_absent_deletes_a_cluster_that_fails_while_waiting(status):
    client = eks_client()
    client.delete_cluster = Mock()
    module = FakeModule({"name": "example", "wait": False, "wait_delay": 15, "wait_timeout": 1200})
    cluster = {"name": "example", "arn": "arn:example"}
    with (
        Stubber(client) as stubber,
        patch.object(
            plugin,
            "describe_cluster",
            side_effect=[
                dict(cluster, status=status),
                dict(cluster, status="FAILED"),
                dict(cluster, status="FAILED"),
                dict(cluster, status="DELETING"),
            ],
        ),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "wait_for_cluster_updates"),
        pytest.raises(ModuleExit) as raised,
    ):
        # The native waiter stops as soon as the cluster reports FAILED.
        stubber.add_response("describe_cluster", {"cluster": dict(cluster, status="FAILED")}, {"name": "example"})
        plugin.ensure_absent(client, module)

    stubber.assert_no_pending_responses()
    client.delete_cluster.assert_called_once_with(name="example", aws_retry=True)
    assert raised.value.values["changed"] is True
    assert raised.value.values["cluster"]["status"] == "DELETING"


@pytest.mark.parametrize("status", ["CREATING", "UPDATING"])
def test_absent_reports_absent_when_a_waited_cluster_disappears(status):
    client = eks_client()
    client.delete_cluster = Mock()
    module = FakeModule({"name": "example", "wait": False, "wait_delay": 15, "wait_timeout": 1200})
    cluster = {"name": "example", "arn": "arn:example"}
    with (
        Stubber(client) as stubber,
        patch.object(plugin, "describe_cluster", side_effect=[dict(cluster, status=status), None, None]),
        patch.object(plugin, "wait_for_cluster_updates") as wait_for_updates,
        pytest.raises(ModuleExit) as raised,
    ):
        # The native waiter stops when DescribeCluster reports the cluster is gone.
        stubber.add_client_error(
            "describe_cluster",
            service_error_code="ResourceNotFoundException",
            expected_params={"name": "example"},
        )
        plugin.ensure_absent(client, module)

    stubber.assert_no_pending_responses()
    wait_for_updates.assert_not_called()
    client.delete_cluster.assert_not_called()
    assert raised.value.values["changed"] is False
    assert raised.value.values["cluster"] == {}
    assert raised.value.values["state"] == "absent"


def test_tagging_uses_the_validated_cluster_arn():
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "tags": {}}
    client = Mock()
    module = FakeModule(eks_params(tags={"Name": "example"}))
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    client.tag_resource.assert_called_once_with(resourceArn="arn:example", tags={"Name": "example"}, aws_retry=True)
    assert raised.value.values["changed"] is True


def test_absent_still_fails_when_a_waited_cluster_is_not_failed():
    client = eks_client()
    module = FakeModule({"name": "example", "wait": False, "wait_delay": 15, "wait_timeout": 1200})
    cluster = {"name": "example", "arn": "arn:example"}
    with (
        Stubber(client) as stubber,
        patch.object(
            plugin,
            "describe_cluster",
            side_effect=[dict(cluster, status="CREATING"), dict(cluster, status="DELETING")],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        stubber.add_response("describe_cluster", {"cluster": dict(cluster, status="DELETING")}, {"name": "example"})
        plugin.ensure_absent(client, module)

    stubber.assert_no_pending_responses()
    assert raised.value.values["msg"] == "Unable to wait for AWS EKS cluster example to become active"
    assert raised.value.values["changed"] is False


def test_check_mode_create_omits_unreturned_bootstrap_setting():
    module = FakeModule(
        eks_params(
            bootstrap_self_managed_addons=True,
            resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
            role_arn="arn:role",
        ),
        check_mode=True,
    )
    with patch.object(plugin, "describe_cluster", return_value=None), pytest.raises(ModuleExit) as raised:
        plugin.ensure_present(Mock(), module)

    assert "bootstrap_self_managed_addons" not in raised.value.values["cluster"]
    assert raised.value.values["cluster"]["role_arn"] == "arn:role"


def test_failure_after_create_reports_changed():
    waiter = Mock()
    waiter.wait.side_effect = WaiterError("cluster_active", "terminal failure state", {})
    client = Mock(get_waiter=Mock(return_value=waiter))
    client.create_cluster.return_value = {"cluster": {"arn": "arn:example", "name": "example", "status": "CREATING"}}
    module = FakeModule(
        eks_params(
            resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
            role_arn="arn:role",
            wait=True,
            wait_delay=15,
            wait_timeout=1200,
        ),
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=None),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True


def test_failure_after_an_update_reports_changed():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "deletionProtection": False,
        "tags": {"Old": "value"},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    client.untag_resource.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "UntagResource"
    )
    module = FakeModule(eks_params(deletion_protection=True, tags={}))
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    assert raised.value.values["msg"] == "Unable to remove tags from EKS cluster example"


def test_first_update_failure_reports_unchanged():
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "deletionProtection": False}
    client = Mock()
    client.update_cluster_config.side_effect = plugin.ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "UpdateClusterConfig"
    )
    module = FakeModule(eks_params(deletion_protection=True))
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False


def test_sdk_requirements_are_checked_before_the_first_update():
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "deletionProtection": False}
    client = Mock()
    module = FakeModule(eks_params(deletion_protection=True, tags={"New": "value"}))

    def require(module, client, service, methods):
        if "tag_resource" in methods:
            module.fail_json(msg="unsupported")

    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail),
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_not_called()


def test_update_wait_support_is_checked_before_the_first_update():
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "deletionProtection": False}
    client = Mock()
    module = FakeModule(eks_params(deletion_protection=True, wait=True))

    def require(module, client, service, methods, changed=False):
        if "describe_update" in methods:
            module.fail_json(changed=changed, msg="unsupported")

    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_cluster_config.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"deletion_protection": True, "version": "1.31"},
        {"deletion_protection": True, "resources_vpc_config": {"endpoint_public_access": False}},
        {"version": "1.31", "wait": True},
    ],
)
def test_update_wait_support_is_checked_before_any_waited_update(overrides):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "deletionProtection": False,
        "resourcesVpcConfig": {"endpointPublicAccess": True},
        "version": "1.30",
    }
    client = Mock()
    module = FakeModule(eks_params(**overrides))

    def require(module, client, service, methods, changed=False):
        if "describe_update" in methods:
            module.fail_json(changed=changed, msg="unsupported")

    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods", side_effect=require),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is False
    client.update_cluster_config.assert_not_called()
    client.update_cluster_version.assert_not_called()


def test_failed_update_wait_reports_changed():
    client = Mock(describe_update=Mock(return_value={"update": {"id": "update-1", "status": "Failed"}}))
    module = FakeModule({"name": "example", "wait_delay": 1, "wait_timeout": 10})
    with patch.object(plugin, "require_client_methods"), pytest.raises(ModuleFail) as raised:
        plugin.wait_for_update(client, module, "update-1", changed=True)

    assert raised.value.values["changed"] is True


def test_cluster_updates_describe_history_once_and_poll_only_in_progress_updates():
    client = Mock()
    module = FakeModule({"name": "example", "wait_delay": 1, "wait_timeout": 60})
    client.describe_update.side_effect = [
        {"update": {"id": "old", "status": "Successful"}},
        {"update": {"id": "first", "status": "InProgress"}},
        {"update": {"id": "second", "status": "InProgress"}},
        {"update": {"id": "first", "status": "Successful"}},
        {"update": {"id": "second", "status": "InProgress"}},
        {"update": {"id": "second", "status": "Failed"}},
    ]
    with (
        patch.object(plugin, "require_client_methods") as require,
        patch.object(plugin, "paginated_query_with_retries", return_value={"updateIds": ["old", "first", "second"]}),
        patch.object(plugin.time, "sleep") as sleep,
    ):
        plugin.wait_for_cluster_updates(client, module)

    require.assert_called_once_with(
        module,
        client,
        "EKS",
        {
            "describe_update": ("name", "updateId"),
            "list_updates": ("maxResults", "name", "nextToken"),
        },
    )
    assert [c.kwargs["updateId"] for c in client.describe_update.call_args_list] == [
        "old",
        "first",
        "second",
        "first",
        "second",
        "second",
    ]
    assert sleep.call_count == 2


def test_cluster_updates_share_one_deadline():
    client = Mock()
    client.describe_update.side_effect = lambda **kwargs: {"update": {"id": kwargs["updateId"], "status": "InProgress"}}
    module = FakeModule({"name": "example", "wait_delay": 5, "wait_timeout": 10})
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"updateIds": ["first", "second"]}),
        patch.object(plugin.time, "monotonic", side_effect=[0, 5, 5, 10]),
        patch.object(plugin.time, "sleep"),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.wait_for_cluster_updates(client, module)

    assert raised.value.values["msg"] == "Timed out waiting for AWS EKS cluster updates first, second for example"
    assert client.describe_update.call_count == 4


def run_absent(params, described, check_mode=False):
    client = Mock()
    module = FakeModule(
        dict({"name": "example", "wait_delay": 15, "wait_timeout": 1200}, **params), check_mode=check_mode
    )
    with (
        patch.object(plugin, "describe_cluster", side_effect=described) as describe,
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        patch.object(plugin, "wait_for_cluster_updates"),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_absent(client, module)

    return client, module, describe, wait_for_cluster, raised.value.values


def test_absent_with_wait_returns_an_empty_cluster_after_deletion():
    client, module, _describe, wait_for_cluster, result = run_absent(
        {"wait": True}, [{"name": "example", "status": "ACTIVE"}]
    )

    client.delete_cluster.assert_called_once_with(name="example", aws_retry=True)
    wait_for_cluster.assert_called_once_with(client, module, "cluster_deleted", changed=True, deadline=ANY)
    assert result["changed"] is True
    assert result["cluster"] == {}


@pytest.mark.parametrize(
    ("reread", "expected"),
    [
        ({"name": "example", "status": "DELETING"}, {"name": "example", "status": "DELETING"}),
        (None, {}),
    ],
)
def test_absent_without_wait_returns_the_cluster_as_it_is_being_deleted(reread, expected):
    client, _module, describe, wait_for_cluster, result = run_absent(
        {"wait": False}, [{"name": "example", "status": "ACTIVE"}, reread]
    )

    client.delete_cluster.assert_called_once_with(name="example", aws_retry=True)
    wait_for_cluster.assert_not_called()
    assert describe.call_args_list[1].kwargs == {"changed": True}
    assert result["changed"] is True
    assert result["cluster"] == expected


@pytest.mark.parametrize(
    ("wait", "expected"),
    [
        (True, {}),
        (False, {"name": "example", "status": "DELETING"}),
    ],
)
def test_absent_check_mode_predicts_the_deleted_cluster(wait, expected):
    client, _module, describe, wait_for_cluster, result = run_absent(
        {"wait": wait}, [{"name": "example", "status": "ACTIVE"}], check_mode=True
    )

    client.delete_cluster.assert_not_called()
    wait_for_cluster.assert_not_called()
    assert describe.call_count == 1
    assert result["changed"] is True
    assert result["cluster"] == expected


@pytest.mark.parametrize(
    ("wait", "check_mode", "waited", "expected"),
    [
        (True, False, True, {}),
        (True, True, False, {}),
        (False, False, False, {"name": "example", "status": "DELETING"}),
        (False, True, False, {"name": "example", "status": "DELETING"}),
    ],
)
def test_absent_in_progress_delete_returns_a_result_consistent_with_wait(wait, check_mode, waited, expected):
    client, _module, _describe, wait_for_cluster, result = run_absent(
        {"wait": wait}, [{"name": "example", "status": "DELETING"}], check_mode=check_mode
    )

    client.delete_cluster.assert_not_called()
    assert wait_for_cluster.called is waited
    assert result["changed"] is False
    assert result["cluster"] == expected


@pytest.mark.parametrize(
    "cidrs, expected",
    [
        (["52.94.76.5/24"], ["52.94.76.0/24"]),
        (["0.0.0.0/0", "2001:db8::1/32"], ["0.0.0.0/0", "2001:db8::/32"]),
        (["52.94.76.5/24", "0.0.0.0/0", "52.94.76.0/24", "0.0.0.0/0"], ["52.94.76.0/24", "0.0.0.0/0"]),
    ],
)
def test_public_access_cidrs_are_canonicalized(cidrs, expected):
    module = FakeModule(eks_params(resources_vpc_config={"public_access_cidrs": cidrs}))

    plugin.canonicalize_public_access_cidrs(module)

    assert module.params["resources_vpc_config"]["public_access_cidrs"] == expected


def test_invalid_public_access_cidr_fails():
    module = FakeModule(eks_params(resources_vpc_config={"public_access_cidrs": ["not-a-cidr"]}))

    with pytest.raises(ModuleFail) as raised:
        plugin.canonicalize_public_access_cidrs(module)

    assert raised.value.values["msg"].startswith("resources_vpc_config.public_access_cidrs must contain valid")


def test_canonical_public_access_cidr_matches_the_cluster():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "resourcesVpcConfig": {"publicAccessCidrs": ["52.94.76.0/24"]},
    }
    client = Mock()
    module = FakeModule(eks_params(resources_vpc_config={"public_access_cidrs": ["52.94.76.5/24"]}))
    plugin.canonicalize_public_access_cidrs(module)
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_not_called()
    assert raised.value.values["changed"] is False


def test_explicitly_disabled_auto_mode_matches_a_standard_cluster():
    # EKS omits computeConfig and storageConfig on clusters that never enabled Auto Mode.
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": False}},
    }
    client = Mock()
    module = FakeModule(
        eks_params(
            compute_config={"enabled": False},
            kubernetes_network_config={"elastic_load_balancing": {"enabled": False}},
            storage_config={"block_storage": {"enabled": False}},
        )
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_not_called()
    assert raised.value.values["changed"] is False


def test_enabling_auto_mode_on_a_standard_cluster_sends_every_capability():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": False}},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            compute_config={"enabled": True},
            kubernetes_network_config={"elastic_load_balancing": {"enabled": True}},
            storage_config={"block_storage": {"enabled": True}},
        )
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    client.update_cluster_config.assert_called_once_with(
        name="example",
        computeConfig={"enabled": True},
        kubernetesNetworkConfig={"elasticLoadBalancing": {"enabled": True}},
        storageConfig={"blockStorage": {"enabled": True}},
    )


@pytest.mark.parametrize("check_mode", [False, True])
def test_disabled_zonal_shift_matches_a_cluster_that_never_set_it(check_mode):
    # EKS returns zonalShiftConfig as null, which botocore drops, until zonal shift is configured.
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "deletionProtection": False}
    client = Mock()
    module = FakeModule(eks_params(zonal_shift_config={"enabled": False}), check_mode=check_mode)
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert client.mock_calls == []
    assert raised.value.values["changed"] is False


@pytest.mark.parametrize("check_mode", [False, True])
def test_enabling_zonal_shift_on_a_cluster_that_never_set_it_sends_an_update(check_mode):
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE", "deletionProtection": False}
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(eks_params(zonal_shift_config={"enabled": True}), check_mode=check_mode)
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    if check_mode:
        client.update_cluster_config.assert_not_called()
        assert raised.value.values["cluster"]["zonal_shift_config"] == {"enabled": True}
    else:
        client.update_cluster_config.assert_called_once_with(name="example", zonalShiftConfig={"enabled": True})


@pytest.mark.parametrize("check_mode", [False, True])
def test_disabled_compute_config_without_node_pools_matches_a_standard_cluster(check_mode):
    # EKS returns computeConfig as null, which botocore drops, on a cluster that never enabled Auto Mode.
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": False}},
    }
    client = Mock()
    module = FakeModule(eks_params(compute_config={"enabled": False, "node_pools": []}), check_mode=check_mode)
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert client.mock_calls == []
    assert raised.value.values["changed"] is False


@pytest.mark.parametrize("check_mode", [False, True])
def test_compute_config_node_pools_on_a_standard_cluster_send_an_update(check_mode):
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "kubernetesNetworkConfig": {"ipFamily": "ipv4", "elasticLoadBalancing": {"enabled": False}},
    }
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            compute_config={"enabled": True, "node_pools": ["general-purpose"], "node_role_arn": "arn:node"},
            kubernetes_network_config={"elastic_load_balancing": {"enabled": True}},
            storage_config={"block_storage": {"enabled": True}},
        ),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    if check_mode:
        client.update_cluster_config.assert_not_called()
    else:
        client.update_cluster_config.assert_called_once_with(
            name="example",
            computeConfig={"enabled": True, "nodePools": ["general-purpose"], "nodeRoleArn": "arn:node"},
            kubernetesNetworkConfig={"elasticLoadBalancing": {"enabled": True}},
            storageConfig={"blockStorage": {"enabled": True}},
        )


@pytest.mark.parametrize("check_mode", [False, True])
def test_empty_remote_network_config_matches_a_cluster_without_remote_networks(check_mode):
    # EKS omits remoteNetworkConfig on a cluster created without hybrid nodes.
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE"}
    client = Mock()
    module = FakeModule(
        eks_params(remote_network_config={"remote_node_networks": [], "remote_pod_networks": []}),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert client.mock_calls == []
    assert raised.value.values["changed"] is False


@pytest.mark.parametrize("check_mode", [False, True])
def test_remote_node_networks_on_a_cluster_without_remote_networks_send_the_whole_config(check_mode):
    current = {"name": "example", "arn": "arn:example", "status": "ACTIVE"}
    client = Mock()
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module = FakeModule(
        eks_params(
            remote_network_config={"remote_node_networks": [{"cidrs": ["10.80.0.0/16"]}], "remote_pod_networks": []}
        ),
        check_mode=check_mode,
    )
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["changed"] is True
    if check_mode:
        client.update_cluster_config.assert_not_called()
    else:
        client.update_cluster_config.assert_called_once_with(
            name="example",
            remoteNetworkConfig={"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16"]}], "remotePodNetworks": []},
        )


@pytest.mark.parametrize("wait", [True, False])
@pytest.mark.parametrize(
    "remote_network_config",
    [
        {"remote_node_networks": [], "remote_pod_networks": []},
        {"remote_node_networks": [], "remote_pod_networks": None},
        {"remote_node_networks": None, "remote_pod_networks": []},
        {"remote_node_networks": None, "remote_pod_networks": None},
    ],
)
def test_create_omits_a_remote_network_config_without_networks(remote_network_config, wait):
    # CreateCluster rejects remoteNetworkConfig without remote node networks (live), so empty lists mean none.
    params = eks_params(
        remote_network_config=remote_network_config,
        resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
        role_arn="arn:role",
        wait=wait,
    )
    client = Mock(create_cluster=Mock(return_value={"cluster": CREATED_CLUSTER}))
    client, real = run_present(FakeModule(params), [None, DESCRIBED_CLUSTER], client)
    check_client, check = run_present(FakeModule(params, check_mode=True), [None])

    client.create_cluster.assert_called_once_with(
        name="example",
        resourcesVpcConfig={"subnetIds": ["subnet-1", "subnet-2"]},
        roleArn="arn:role",
        aws_retry=True,
    )
    assert check_client.mock_calls == []
    assert check["changed"] is real["changed"] is True
    assert "remote_network_config" not in real["cluster"]
    assert "remote_network_config" not in check["cluster"]


@pytest.mark.parametrize("wait", [True, False])
@pytest.mark.parametrize(
    "remote_network_config, expected",
    [
        # CreateCluster rejects an empty remotePodNetworks list: "Remote pod network can't be empty" (live).
        (
            {"remote_node_networks": [{"cidrs": ["10.80.0.0/16"]}], "remote_pod_networks": []},
            {"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16"]}]},
        ),
        (
            {
                "remote_node_networks": [{"cidrs": ["10.80.0.0/16"]}],
                "remote_pod_networks": [{"cidrs": ["10.81.0.0/16"]}],
            },
            {"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16"]}], "remotePodNetworks": [{"cidrs": ["10.81.0.0/16"]}]},
        ),
    ],
    ids=["empty-pods", "nodes-and-pods"],
)
def test_create_sends_remote_networks_without_empty_lists(remote_network_config, expected, wait):
    params = eks_params(
        remote_network_config=remote_network_config,
        resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
        role_arn="arn:role",
        wait=wait,
    )
    # CreateCluster and DescribeCluster return only the remote network lists the create sent (live).
    created = dict(CREATED_CLUSTER, remoteNetworkConfig=expected)
    described = dict(DESCRIBED_CLUSTER, remoteNetworkConfig=expected)
    client = Mock(create_cluster=Mock(return_value={"cluster": created}))
    client, real = run_present(FakeModule(params), [None, described], client)
    check_client, check = run_present(FakeModule(params, check_mode=True), [None])

    assert client.create_cluster.call_args.kwargs["remoteNetworkConfig"] == expected
    assert check_client.mock_calls == []
    assert check["changed"] is real["changed"] is True
    assert check["cluster"]["remote_network_config"] == real["cluster"]["remote_network_config"]
    assert check["cluster"]["remote_network_config"] == plugin.boto3_resource_to_ansible_dict(
        expected, force_tags=False
    )


def test_empty_remote_network_lists_still_remove_the_remote_networks_of_an_existing_cluster():
    current = {
        "name": "example",
        "arn": "arn:example",
        "status": "ACTIVE",
        "remoteNetworkConfig": {"remoteNodeNetworks": [{"cidrs": ["10.80.0.0/16"]}], "remotePodNetworks": []},
    }
    params = eks_params(remote_network_config={"remote_node_networks": [], "remote_pod_networks": []})

    client, result = run_present(FakeModule(params), [current])

    assert result["changed"] is True
    client.update_cluster_config.assert_called_once_with(
        name="example",
        remoteNetworkConfig={"remoteNodeNetworks": [], "remotePodNetworks": []},
    )


NODE_NETWORKS = [{"cidrs": ["10.80.0.0/16"]}]
POD_NETWORKS = [{"cidrs": ["10.81.0.0/16"]}]


@pytest.mark.parametrize("wait", [True, False])
@pytest.mark.parametrize(
    "current_config, remote_network_config, described_config",
    [
        # DescribeCluster omits remoteNetworkConfig once both lists are removed (live).
        (
            {"remoteNodeNetworks": NODE_NETWORKS, "remotePodNetworks": POD_NETWORKS},
            {"remote_node_networks": [], "remote_pod_networks": []},
            None,
        ),
        # DescribeCluster omits an empty remotePodNetworks (live).
        (
            None,
            {"remote_node_networks": NODE_NETWORKS, "remote_pod_networks": []},
            {"remoteNodeNetworks": NODE_NETWORKS},
        ),
        # UpdateClusterConfig keeps the node networks when they are omitted (live).
        (
            {"remoteNodeNetworks": NODE_NETWORKS, "remotePodNetworks": [{"cidrs": ["10.82.0.0/16"]}]},
            {"remote_node_networks": None, "remote_pod_networks": POD_NETWORKS},
            {"remoteNodeNetworks": NODE_NETWORKS, "remotePodNetworks": POD_NETWORKS},
        ),
    ],
    ids=["remove", "nodes-with-empty-pods", "pods-only"],
)
def test_remote_network_update_predicts_the_configuration_eks_returns(
    current_config, remote_network_config, described_config, wait
):
    def cluster(config):
        return dict(STANDARD_CLUSTER, remoteNetworkConfig=config) if config is not None else STANDARD_CLUSTER

    params = eks_params(remote_network_config=remote_network_config, wait=wait)

    client, real = run_present(FakeModule(params), [cluster(current_config), cluster(described_config)])
    check_client, check = run_present(FakeModule(params, check_mode=True), [cluster(current_config)])

    client.update_cluster_config.assert_called_once()
    assert check_client.mock_calls == []
    assert check == real
    if described_config is None:
        assert "remote_network_config" not in check["cluster"]
    else:
        assert check["cluster"]["remote_network_config"] == plugin.boto3_resource_to_ansible_dict(
            described_config, force_tags=False
        )


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "current_config, remote_network_config",
    [
        # UpdateClusterConfig: "remoteNodeNetworks can only be empty if the remotePodNetworks is also empty" (live).
        (
            {"remoteNodeNetworks": NODE_NETWORKS, "remotePodNetworks": POD_NETWORKS},
            {"remote_node_networks": [], "remote_pod_networks": None},
        ),
        ({"remoteNodeNetworks": NODE_NETWORKS}, {"remote_node_networks": [], "remote_pod_networks": None}),
        (
            {"remoteNodeNetworks": NODE_NETWORKS, "remotePodNetworks": POD_NETWORKS},
            {"remote_node_networks": [], "remote_pod_networks": POD_NETWORKS},
        ),
        # UpdateClusterConfig: "Remote node networks must be provided" (live).
        (None, {"remote_node_networks": None, "remote_pod_networks": POD_NETWORKS}),
    ],
    ids=["remove-nodes-keep-pods", "remove-nodes-omit-pods", "remove-nodes-send-pods", "pods-without-nodes"],
)
def test_remote_pod_networks_without_remote_node_networks_fail_before_any_update(
    current_config, remote_network_config, check_mode
):
    # The deletion protection update would otherwise be applied first.
    current = dict(STANDARD_CLUSTER, remoteNetworkConfig=current_config) if current_config else STANDARD_CLUSTER
    params = eks_params(deletion_protection=True, remote_network_config=remote_network_config)
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {
        "msg": "remote_network_config.remote_pod_networks must be an empty list when no remote node networks remain"
    }
    assert client.mock_calls == []


# A cluster created through the API without access_config (live).
CONFIG_MAP_CLUSTER = dict(STANDARD_CLUSTER, accessConfig={"authenticationMode": "CONFIG_MAP"}, deletionProtection=False)


def access_config_params(authentication_mode):
    return {"authentication_mode": authentication_mode, "bootstrap_cluster_creator_admin_permissions": True}


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("access_config", [None, access_config_params("CONFIG_MAP")], ids=["omitted", "config-map"])
def test_remote_networks_on_a_config_map_cluster_fail_before_any_update(access_config, check_mode):
    # UpdateClusterConfig: "Authentication Mode must be API_AND_CONFIG_MAP or API when remoteNetworkConfig is
    # specified" (live), after the deletion protection update had already been applied.
    params = eks_params(
        access_config=access_config,
        deletion_protection=True,
        remote_network_config={"remote_node_networks": NODE_NETWORKS, "remote_pod_networks": None},
    )
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=CONFIG_MAP_CLUSTER),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {
        "msg": "remote_network_config requires access_config.authentication_mode API or API_AND_CONFIG_MAP"
    }
    assert client.mock_calls == []
    wait_for_cluster.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_remote_networks_follow_an_access_change_away_from_config_map(check_mode):
    # The access update is the first update and is waited on before the remote network update.
    params = eks_params(
        access_config=access_config_params("API_AND_CONFIG_MAP"),
        deletion_protection=True,
        remote_network_config={"remote_node_networks": NODE_NETWORKS, "remote_pod_networks": None},
    )

    client, result = run_present(FakeModule(params, check_mode=check_mode), [CONFIG_MAP_CLUSTER])

    assert result["changed"] is True
    assert result["cluster"]["access_config"] == {"authentication_mode": "API_AND_CONFIG_MAP"}
    assert result["cluster"]["remote_network_config"] == {"remote_node_networks": NODE_NETWORKS}
    if check_mode:
        assert client.mock_calls == []
    else:
        assert client.update_cluster_config.call_args_list == [
            call(name="example", accessConfig={"authenticationMode": "API_AND_CONFIG_MAP"}),
            call(name="example", deletionProtection=True),
            call(name="example", remoteNetworkConfig={"remoteNodeNetworks": NODE_NETWORKS}),
        ]


def vpc_config_params(**values):
    config = dict.fromkeys(
        ["endpoint_private_access", "endpoint_public_access", "public_access_cidrs", "security_group_ids", "subnet_ids"]
    )
    config.update(values)
    return config


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("cidrs", [["0.0.0.0/0", "::/0"], ["2001:db8::/32"]], ids=["mixed", "ipv6"])
def test_ipv6_public_access_cidrs_on_an_ipv4_cluster_fail_before_any_update(cidrs, check_mode):
    # UpdateClusterConfig and CreateCluster: "Invalid CIDR: IPv6 CIDR block [::/0] is not supported. An IPv4 cluster or
    # an IPv6 cluster created before October 2024 only supports IPv4 CIDR blocks for the publicAccessCidrs parameter."
    # (live); the endpoint update follows the deletion protection update.
    params = eks_params(deletion_protection=True, resources_vpc_config=vpc_config_params(public_access_cidrs=cidrs))
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=CONFIG_MAP_CLUSTER),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {
        "msg": "resources_vpc_config.public_access_cidrs must not contain IPv6 CIDR blocks for an IPv4 cluster"
    }
    assert client.mock_calls == []
    wait_for_cluster.assert_not_called()


def test_ipv6_public_access_cidrs_reach_aws_for_an_ipv6_cluster():
    # IPv6 clusters made after October 2024 accept them (model).
    cidrs = ["0.0.0.0/0", "::/0"]
    current = dict(
        STANDARD_CLUSTER, kubernetesNetworkConfig={"ipFamily": "ipv6", "elasticLoadBalancing": {"enabled": False}}
    )
    params = eks_params(deletion_protection=True, resources_vpc_config=vpc_config_params(public_access_cidrs=cidrs))

    client, result = run_present(FakeModule(params), [current])

    assert result["changed"] is True
    assert client.update_cluster_config.call_args_list == [
        call(name="example", deletionProtection=True),
        call(name="example", resourcesVpcConfig={"publicAccessCidrs": cidrs}),
    ]


def test_ipv6_public_access_cidrs_on_create_are_left_to_aws():
    # CreateCluster rejects them for an IPv4 cluster before it creates anything (live).
    cidrs = ["0.0.0.0/0", "::/0"]
    params = eks_params(
        resources_vpc_config=vpc_config_params(public_access_cidrs=cidrs, subnet_ids=["subnet-1", "subnet-2"]),
        role_arn="arn:role",
    )
    client = Mock(create_cluster=Mock(return_value={"cluster": CREATED_CLUSTER}))

    client, result = run_present(FakeModule(params), [None], client)

    assert result["changed"] is True
    assert client.create_cluster.call_args.kwargs["resourcesVpcConfig"]["publicAccessCidrs"] == cidrs


def public_cidrs(count):
    return [f"52.0.{index}.0/24" for index in range(count)]


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("cidrs", [public_cidrs(41), public_cidrs(41) + ["52.0.0.5/24"]], ids=["41", "41-and-repeat"])
def test_more_than_forty_public_access_cidrs_fail_before_any_aws_call(cidrs, check_mode):
    # CreateCluster: "The publicAccessCidrs list should not be larger than 40." (live); the quota applies on create and
    # update, and an update sends the endpoint settings after the deletion protection update.
    params = eks_params(
        deletion_protection=True, resources_vpc_config=vpc_config_params(public_access_cidrs=cidrs), state="present"
    )
    module = FakeModule(params, check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": "resources_vpc_config.public_access_cidrs must contain at most 40 CIDR blocks"
    }
    module.client.assert_not_called()


@pytest.mark.parametrize(
    "cidrs", [public_cidrs(40), public_cidrs(40) + ["52.0.0.5/24"]], ids=["40", "40-blocks-and-repeat"]
)
def test_forty_public_access_cidr_blocks_reach_aws(cidrs):
    params = eks_params(resources_vpc_config=vpc_config_params(public_access_cidrs=cidrs), state="present")
    module = FakeModule(params)
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    module.client.assert_called_once()


@pytest.mark.parametrize("check_mode", [False, True])
def test_repeated_public_access_cidr_beyond_forty_entries_matches_the_cluster(check_mode):
    # A list whose 40 distinct blocks match the cluster converges, as it did before repeats were sent once.
    current = dict(STANDARD_CLUSTER, resourcesVpcConfig=dict(STANDARD_CLUSTER["resourcesVpcConfig"]))
    current["resourcesVpcConfig"]["publicAccessCidrs"] = public_cidrs(40)
    params = eks_params(
        resources_vpc_config=vpc_config_params(public_access_cidrs=public_cidrs(40) + ["52.0.0.5/24"]),
        state="present",
    )
    module = FakeModule(params, check_mode=check_mode)
    module.client = Mock(return_value=Mock())
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"] is False
    module.client.return_value.update_cluster_config.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("current", [None, STANDARD_CLUSTER], ids=["create", "update"])
def test_repeated_public_access_cidr_blocks_are_sent_once(current, check_mode):
    # EKS counts every entry against its limit (live: 40 distinct blocks and a repeat are rejected as larger than 40).
    params = eks_params(
        deletion_protection=True,
        resources_vpc_config=vpc_config_params(
            public_access_cidrs=public_cidrs(40) + ["52.0.0.5/24", "52.0.39.0/24"], subnet_ids=["subnet-a", "subnet-b"]
        ),
        role_arn="arn:role",
        state="present",
    )
    module = FakeModule(params, check_mode=check_mode)
    client = Mock(create_cluster=Mock(return_value={"cluster": CREATED_CLUSTER}))
    client.update_cluster_config.return_value = {"update": {"id": "update-1", "status": "InProgress"}}
    module.client = Mock(return_value=client)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        patch.object(plugin, "wait_for_cluster"),
        patch.object(plugin, "wait_for_update"),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"] is True
    if check_mode:
        assert client.mock_calls == []
        assert raised.value.values["cluster"]["resources_vpc_config"]["public_access_cidrs"] == public_cidrs(40)
    elif current is None:
        assert client.create_cluster.call_args.kwargs["resourcesVpcConfig"]["publicAccessCidrs"] == public_cidrs(40)
    else:
        assert client.update_cluster_config.call_args_list == [
            call(name="example", deletionProtection=True),
            call(name="example", resourcesVpcConfig={"publicAccessCidrs": public_cidrs(40)}),
        ]


def cluster_with_endpoints(public, private):
    return dict(
        STANDARD_CLUSTER,
        resourcesVpcConfig={
            "endpointPrivateAccess": private,
            "endpointPublicAccess": public,
            "subnetIds": ["subnet-a", "subnet-b"],
        },
    )


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "current, endpoints",
    [
        (cluster_with_endpoints(public=True, private=False), {"endpoint_public_access": False}),
        (cluster_with_endpoints(public=False, private=True), {"endpoint_private_access": False}),
        (
            cluster_with_endpoints(public=True, private=True),
            {"endpoint_private_access": False, "endpoint_public_access": False},
        ),
    ],
    ids=["public-off", "private-off", "both-off"],
)
def test_disabling_both_api_server_endpoints_fails_before_any_update(current, endpoints, check_mode):
    # UpdateClusterConfig: "Both private and public endpoint access cannot be false" (live), after the deletion
    # protection update had already been applied.
    params = eks_params(deletion_protection=True, resources_vpc_config=vpc_config_params(**endpoints))
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {
        "msg": (
            "resources_vpc_config.endpoint_public_access and resources_vpc_config.endpoint_private_access "
            "must not both be false"
        )
    }
    assert client.mock_calls == []
    wait_for_cluster.assert_not_called()


def test_disabling_one_api_server_endpoint_while_enabling_the_other_reaches_aws():
    params = eks_params(
        resources_vpc_config=vpc_config_params(endpoint_private_access=True, endpoint_public_access=False)
    )

    client, result = run_present(FakeModule(params), [cluster_with_endpoints(public=True, private=False)])

    assert result["changed"] is True
    client.update_cluster_config.assert_called_once_with(
        name="example", resourcesVpcConfig={"endpointPrivateAccess": True, "endpointPublicAccess": False}
    )


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"role_arn": ""}, "role_arn must not be empty"),
        (
            {"resources_vpc_config": {"subnet_ids": ["subnet-1", ""]}},
            "resources_vpc_config.subnet_ids must not contain empty entries",
        ),
        (
            {"resources_vpc_config": {"security_group_ids": ["sg-1", ""], "subnet_ids": ["subnet-1", "subnet-2"]}},
            "resources_vpc_config.security_group_ids must not contain empty entries",
        ),
        ({"version": ""}, "version must not be empty"),
        # EKS: "The publicAccessCidrs list should not be empty." (live, on create and update).
        (
            {"deletion_protection": True, "resources_vpc_config": {"public_access_cidrs": []}},
            "resources_vpc_config.public_access_cidrs must not be empty",
        ),
    ],
)
def test_empty_role_arn_version_and_network_ids_fail_before_any_aws_call(overrides, message, check_mode):
    # EKS rejects them (live), but only after check mode predicted success or other updates were applied. A cluster
    # always has a version, so an empty one would also never converge.
    params = eks_params(state="present", **overrides)
    module = FakeModule(params, check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["msg"] == message
    module.client.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("network", ["remote_node_networks", "remote_pod_networks"])
@pytest.mark.parametrize("cidrs", [[], [""], ["10.82.0.0/16", ""]], ids=["empty", "blank", "blank-entry"])
def test_remote_network_cidrs_that_are_empty_or_blank_fail_before_any_aws_call(cidrs, network, check_mode):
    # EKS rejects them on create and update (live: "CIDRs can not be null or empty when specifying
    # remoteNodeNetworks." and "Invalid remote node network:  is not a valid CIDR"), and an update sends them only
    # after the deletion protection update.
    config = {"remote_node_networks": NODE_NETWORKS, "remote_pod_networks": POD_NETWORKS}
    config[network] = [{"cidrs": cidrs}]
    params = eks_params(deletion_protection=True, remote_network_config=config, state="present")
    module = FakeModule(params, check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": f"remote_network_config.{network}[].cidrs must not be empty or contain empty entries"
    }
    module.client.assert_not_called()


def test_remote_network_cidrs_reach_aws():
    config = {"remote_node_networks": NODE_NETWORKS, "remote_pod_networks": POD_NETWORKS}
    module = FakeModule(eks_params(remote_network_config=config, state="present"))
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    module.client.assert_called_once()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("subnet_ids", [["subnet-1"], ["subnet-1", "subnet-1"]])
def test_create_with_fewer_than_two_distinct_subnets_fails_before_any_aws_call(subnet_ids, check_mode):
    # CreateCluster rejects it with "Subnets specified must be in at least two different AZs" (live).
    params = eks_params(resources_vpc_config={"subnet_ids": subnet_ids}, role_arn="arn:role", wait=True)
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=None),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {"msg": "resources_vpc_config.subnet_ids must contain at least two distinct subnets"}
    assert client.mock_calls == []


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("status", ["ACTIVE", "UPDATING"])
@pytest.mark.parametrize("subnet_ids", [[], ["subnet-a"], ["subnet-a", "subnet-a"]])
def test_subnet_change_to_fewer_than_two_distinct_subnets_fails_before_any_update(subnet_ids, status, check_mode):
    # UpdateClusterConfig rejects it (live), after the deletion protection update had already been applied. It also
    # fails before the wait for an UPDATING cluster to become ACTIVE that precedes any change.
    current = dict(STANDARD_CLUSTER, status=status)
    params = eks_params(deletion_protection=True, resources_vpc_config={"subnet_ids": subnet_ids}, wait=False)
    client = Mock()
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, FakeModule(params, check_mode=check_mode))

    assert raised.value.values == {"msg": "resources_vpc_config.subnet_ids must contain at least two distinct subnets"}
    assert client.mock_calls == []
    wait_for_cluster.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "tags", [{"Team": "R&D"}, {"Team": "a,b"}, {"Team#1": "x"}], ids=["ampersand", "comma", "hash-key"]
)
def test_tag_characters_aws_rejects_fail_before_aws(check_mode, tags):
    # EKS TagResource rejects these with BadRequestException (live), which an update reaches only after its
    # configuration and version updates and the removal of purged tags.
    module = FakeModule(eks_params(deletion_protection=True, state="present", tags=tags), check_mode=check_mode)
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {
        "msg": "tag keys and values must contain only letters, numbers, spaces, and _ . : / = + - @"
    }
    module.client.assert_not_called()


def test_tags_with_characters_aws_accepts_reach_aws():
    # EKS TagResource accepts these (live).
    module = FakeModule(eks_params(state="present", tags={"Team": "a b_.:/=+-@é1", "日本": "٣²"}))
    module.client = Mock(side_effect=ModuleInitialized)
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleInitialized),
    ):
        plugin.main()

    module.client.assert_called_once()


def fake_clock():
    """Return a clock whose sleep and waiter calls advance it, and the patches that install it."""
    clock = {"now": 0}

    def sleep(seconds):
        clock["now"] += seconds

    return clock, (
        patch.object(plugin.time, "monotonic", side_effect=lambda: clock["now"]),
        patch.object(plugin.time, "sleep", side_effect=sleep),
    )


def test_update_waits_share_one_wait_timeout_budget():
    # The first update takes 30 of 100 seconds and the cluster 20 more, so the second update has 50 left.
    clock, clock_patches = fake_clock()
    client = Mock()
    client.update_cluster_config.side_effect = [
        {"update": {"id": "update-1", "status": "InProgress"}},
        {"update": {"id": "update-2", "status": "InProgress"}},
    ]
    attempts = []

    def wait(name, WaiterConfig):
        attempts.append(WaiterConfig["MaxAttempts"])
        clock["now"] += 20

    client.get_waiter.return_value = Mock(wait=Mock(side_effect=wait))

    def describe_update(client, module, update_id, changed=False):
        succeeded = update_id == "update-1" and clock["now"] >= 30
        return {"id": update_id, "status": "Successful" if succeeded else "InProgress"}

    module = FakeModule(
        eks_params(
            resources_vpc_config={"endpoint_public_access": False, "subnet_ids": ["subnet-new-a", "subnet-new-b"]},
            wait=True,
            wait_delay=10,
            wait_timeout=100,
        )
    )
    current = {
        "arn": "arn:example",
        "name": "example",
        "resourcesVpcConfig": {"endpointPublicAccess": True, "subnetIds": ["subnet-old-a", "subnet-old-b"]},
        "status": "ACTIVE",
    }
    with (
        patch.object(plugin, "describe_cluster", return_value=current),
        patch.object(plugin, "describe_update", side_effect=describe_update),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        clock_patches[0],
        clock_patches[1],
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.ensure_present(client, module)

    assert raised.value.values["msg"] == "Timed out waiting for AWS EKS cluster update update-2 for example"
    assert raised.value.values["changed"] is True
    # The cluster waiter keeps its attempts arithmetic, bounded by the 70 seconds left after the first update.
    assert attempts == [8]
    assert clock["now"] == 100


def test_recreating_a_deleting_cluster_shares_one_wait_timeout_budget():
    clock, clock_patches = fake_clock()
    attempts = []

    def wait(name, WaiterConfig):
        attempts.append(WaiterConfig["MaxAttempts"])
        clock["now"] += 60

    client = Mock(get_waiter=Mock(return_value=Mock(wait=Mock(side_effect=wait))))
    client.create_cluster.return_value = {"cluster": {"arn": "arn:example", "name": "example", "status": "CREATING"}}
    module = FakeModule(
        eks_params(
            resources_vpc_config={"subnet_ids": ["subnet-1", "subnet-2"]},
            role_arn="arn:role",
            wait=True,
            wait_delay=10,
            wait_timeout=100,
        )
    )
    active = {"arn": "arn:example", "name": "example", "status": "ACTIVE"}
    with (
        patch.object(plugin, "describe_cluster", side_effect=[{"name": "example", "status": "DELETING"}, None, active]),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "require_nested_request_parameters"),
        clock_patches[0],
        clock_patches[1],
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_present(client, module)

    assert [waiter_call.args[0] for waiter_call in client.get_waiter.call_args_list] == [
        "cluster_deleted",
        "cluster_active",
    ]
    # Waiting out the deletion leaves 40 of 100 seconds for the new cluster.
    assert attempts == [11, 5]


def test_an_exhausted_wait_timeout_budget_fails_the_cluster_wait():
    waiter = Mock()
    module = FakeModule({"name": "example", "wait_delay": 10, "wait_timeout": 100})
    with patch.object(plugin.time, "monotonic", return_value=101), pytest.raises(ModuleFail) as raised:
        plugin.wait_for_cluster(
            Mock(get_waiter=Mock(return_value=waiter)), module, "cluster_active", changed=True, deadline=100.5
        )

    waiter.wait.assert_not_called()
    assert raised.value.values == {
        "changed": True,
        "msg": "Unable to wait for AWS EKS cluster example to become active",
    }


def test_absent_waits_share_one_wait_timeout_budget():
    clock, clock_patches = fake_clock()
    attempts = []

    def wait(name, WaiterConfig):
        attempts.append(WaiterConfig["MaxAttempts"])
        clock["now"] += 30

    client = Mock(get_waiter=Mock(return_value=Mock(wait=Mock(side_effect=wait))))
    module = FakeModule({"name": "example", "wait": True, "wait_delay": 10, "wait_timeout": 100})
    updating = {"arn": "arn:example", "name": "example", "status": "UPDATING"}
    with (
        patch.object(plugin, "describe_cluster", side_effect=[updating, dict(updating, status="ACTIVE")]),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "paginated_query_with_retries", return_value={"updateIds": ["update-1"]}),
        patch.object(
            plugin,
            "describe_update",
            side_effect=lambda client, module, update_id, changed=False: {
                "id": update_id,
                "status": "Successful" if clock["now"] >= 50 else "InProgress",
            },
        ),
        clock_patches[0],
        clock_patches[1],
        pytest.raises(ModuleExit),
    ):
        plugin.ensure_absent(client, module)

    # 30 seconds for the cluster to become active and 20 for its update leave 50 seconds for the deletion.
    assert attempts == [11, 6]
