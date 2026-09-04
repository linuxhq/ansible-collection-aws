from unittest import TestCase
from unittest.mock import Mock, call, patch

from ansible_collections.linuxhq.aws.plugins.modules import eks_cluster as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class EksClusterTests(TestCase):
    def test_sdk_validation_starts_with_lookup_only(self):
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

    def test_sdk_validation_checks_nested_vpc_parameters(self):
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

        self.assertTrue(
            any(
                "resourcesVpcConfig parameter endpointPublicAccess" in call.kwargs["msg"]
                for call in module.fail_json.call_args_list
            )
        )

    def test_tag_limits_are_rejected_before_client_creation(self):
        module = FakeModule(
            {
                "encryption_config": None,
                "state": "present",
                "tags": {str(index): "" for index in range(51)},
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(raised.exception.values["msg"], "tags must contain at most 50 entries")

    def test_absent_does_not_validate_unused_create_options(self):
        params = dict.fromkeys(plugin.CREATE_FIELDS)
        params.update(
            {
                "encryption_config": [{}, {}],
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

    def test_multiple_encryption_configs_are_rejected(self):
        module = FakeModule({"encryption_config": [{}, {}], "state": "present"})
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertEqual(
            raised.exception.values["msg"],
            "encryption_config must contain at most one entry",
        )

    def test_absent_tolerates_cluster_disappearing_during_delete(self):
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
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        require.assert_called_once_with(module, client, "EKS", {"delete_cluster": ("name",)})
        self.assertTrue(raised.exception.values["changed"])

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["argument_spec"]["wait_timeout"]["default"] == 1200
        assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]

    def test_describe_rejects_malformed_response(self):
        client = Mock(describe_cluster=Mock(return_value={"cluster": None}))
        module = FakeModule({"name": "example"})
        with self.assertRaises(ModuleFail) as raised:
            plugin.describe_cluster(client, module)
        self.assertEqual(raised.exception.values["msg"], "EKS returned an invalid cluster")

    def test_describe_rejects_malformed_cluster_configuration(self):
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
        with self.assertRaises(ModuleFail) as raised:
            plugin.describe_cluster(client, module)
        self.assertEqual(raised.exception.values["msg"], "EKS returned an invalid cluster")

    def test_update_validation_rejects_malformed_response(self):
        module = FakeModule({"name": "example"})
        with self.assertRaises(ModuleFail) as raised:
            plugin.validate_update(module, {"id": "update-1"})
        self.assertEqual(raised.exception.values["msg"], "EKS returned an invalid cluster update")

    def test_waited_update_rejects_disappearing_cluster(self):
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
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertEqual(
            raised.exception.values["msg"],
            "EKS cluster example disappeared after update",
        )

    def test_changed_request_contains_only_differences(self):
        current = {"version": "1.32", "resources": {"public": True, "private": False}}
        desired = {"version": "1.32", "resources": {"public": False}}
        assert plugin.changed_request(current, desired) == {"resources": {"public": False}}

    def test_changed_ignores_list_order_and_duplicates(self):
        self.assertFalse(
            plugin.changed(
                ["subnet-2", "subnet-1"],
                ["subnet-1", "subnet-2", "subnet-1"],
            )
        )

    def test_enabled_log_types_flattens_enabled_entries(self):
        assert plugin.enabled_log_types(
            {
                "clusterLogging": [
                    {"enabled": True, "types": ["api", "audit"]},
                    {"enabled": False, "types": ["scheduler"]},
                ]
            }
        ) == {"api", "audit"}

    def test_vpc_endpoint_and_network_changes_use_separate_updates(self):
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
                    "subnet_ids": ["subnet-new"],
                },
                "tags": None,
                "wait": False,
            }
        )
        module = FakeModule(params)
        current = {
            "name": "example",
            "resourcesVpcConfig": {
                "endpointPublicAccess": True,
                "subnetIds": ["subnet-old"],
            },
            "status": "ACTIVE",
        }
        with (
            patch.object(plugin, "describe_cluster", side_effect=[current, current]),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "require_nested_request_parameters") as nested,
            patch.object(plugin, "wait_for_update") as wait_for_update,
            patch.object(plugin, "wait_for_cluster"),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            [call.kwargs for call in client.update_cluster_config.call_args_list],
            [
                {
                    "name": "example",
                    "resourcesVpcConfig": {"endpointPublicAccess": False},
                    "aws_retry": True,
                },
                {
                    "name": "example",
                    "resourcesVpcConfig": {"subnetIds": ["subnet-new"]},
                    "aws_retry": True,
                },
            ],
        )
        self.assertEqual(
            require.call_args_list,
            [
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
            ],
        )
        self.assertEqual(nested.call_count, 2)
        wait_for_update.assert_called_once_with(client, module, "update-1")
        self.assertEqual(
            raised.exception.values["cluster"]["resources_vpc_config"],
            {"endpoint_public_access": False, "subnet_ids": ["subnet-new"]},
        )

    def test_check_mode_preserves_unmanaged_tags(self):
        fields = dict.fromkeys(plugin.CREATE_FIELDS)
        fields.update(
            {
                "name": "example",
                "purge_tags": False,
                "tags": {"managed": "new"},
            }
        )
        current = {"name": "example", "tags": {"keep": "yes", "managed": "old"}}

        self.assertEqual(
            plugin.check_mode_cluster(FakeModule(fields), current)["tags"],
            {"keep": "yes", "managed": "new"},
        )

    def test_additive_tags_reject_a_result_above_the_provider_limit(self):
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
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(client, FakeModule(params))
        self.assertEqual(
            raised.exception.values["msg"],
            "The resulting cluster tags must contain at most 50 entries",
        )
        client.tag_resource.assert_not_called()

    def test_no_wait_change_waits_for_active_cluster_and_rechecks_state(self):
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
            "name": "example",
            "resourcesVpcConfig": {"endpointPublicAccess": True},
            "status": "UPDATING",
        }
        active = {
            "name": "example",
            "resourcesVpcConfig": {"endpointPublicAccess": False},
            "status": "ACTIVE",
        }
        module = FakeModule(params)
        with (
            patch.object(plugin, "describe_cluster", side_effect=[transitioning, active]),
            patch.object(plugin, "wait_for_cluster") as wait_for_cluster,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)

        wait_for_cluster.assert_called_once_with(client, module, "cluster_active")
        client.update_cluster_config.assert_not_called()
        self.assertFalse(raised.exception.values["changed"])

    def test_deleting_cluster_waits_then_recreates(self):
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
                "resources_vpc_config": {"subnet_ids": ["subnet-1"]},
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
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)
        wait_for_cluster.assert_called_once_with(client, module, "cluster_deleted")
        self.assertEqual(
            require.call_args.args[3],
            {
                "create_cluster": (
                    "resourcesVpcConfig",
                    "roleArn",
                    "name",
                )
            },
        )
        client.create_cluster.assert_called_once()

    def test_absent_does_not_repeat_an_in_progress_delete(self):
        client = Mock()
        module = FakeModule({"name": "example", "wait": False})
        with (
            patch.object(
                plugin,
                "describe_cluster",
                return_value={"name": "example", "status": "DELETING"},
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertFalse(raised.exception.values["changed"])
        client.delete_cluster.assert_not_called()

    def test_new_cluster_requires_role_and_subnets(self):
        base = dict.fromkeys(plugin.CREATE_FIELDS)
        base.update({"name": "example", "tags": None, "wait": False})
        cases = [
            (
                dict(
                    base,
                    resources_vpc_config={"subnet_ids": ["subnet-1"]},
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
                self.subTest(message=message),
                patch.object(plugin, "describe_cluster", return_value=None),
                self.assertRaises(ModuleFail) as raised,
            ):
                plugin.ensure_present(Mock(), FakeModule(params))
            self.assertIn(message, raised.exception.values["msg"])

    def test_failed_update_stops_waiting_with_update_details(self):
        client = Mock(describe_update=Mock(return_value={"update": {"id": "update-1", "status": "Failed"}}))
        module = FakeModule({"name": "example", "wait_delay": 1, "wait_timeout": 10})
        with (
            patch.object(plugin.time, "monotonic", side_effect=[0, 1]),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.wait_for_update(client, module, "update-1")
        require.assert_called_once_with(
            module,
            client,
            "EKS",
            {"describe_update": ("name", "updateId")},
        )
        self.assertEqual(raised.exception.values["update"]["status"], "Failed")

    def test_cluster_waiter_uses_requested_delay(self):
        waiter = Mock()
        module = FakeModule({"name": "example", "wait_delay": 7, "wait_timeout": 20})
        with patch.object(plugin, "get_waiter", return_value=waiter):
            plugin.wait_for_cluster(Mock(), module, "cluster_active")

        waiter.wait.assert_called_once_with(
            name="example",
            WaiterConfig={"Delay": 7, "MaxAttempts": 3},
        )
