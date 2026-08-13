from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import global_accelerator as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
    assert_module_rejects,
)


class GlobalAcceleratorTests(TestCase):
    def test_absent_does_not_validate_unused_present_options(self):
        module = FakeModule(
            {
                "arn": None,
                "idempotency_token": "t" * 256,
                "ip_addresses": ["192.0.2.1"] * 3,
                "listeners": [{"port_ranges": []}],
                "name": "example",
                "state": "absent",
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "ensure_absent") as ensure_absent,
        ):
            plugin.main()

        ensure_absent.assert_called_once_with(None, module)

    def test_absent_tolerates_accelerator_disappearing_during_delete(self):
        client = Mock()
        client.delete_accelerator.side_effect = plugin.ClientError(
            {"Error": {"Code": "AcceleratorNotFoundException", "Message": "gone"}},
            "DeleteAccelerator",
        )
        module = FakeModule({"wait": False})
        with (
            patch.object(
                plugin,
                "get_accelerator",
                return_value={"AcceleratorArn": "arn:accelerator", "Enabled": False},
            ),
            patch.object(plugin, "get_listeners", return_value=[]),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        require.assert_called_once_with(
            module,
            client,
            "Global Accelerator",
            {"delete_accelerator": ("AcceleratorArn",)},
        )
        self.assertTrue(raised.exception.values["changed"])

    def test_absent_tolerates_accelerator_disappearing_while_waiting(self):
        client = Mock()
        module = FakeModule({"wait": False})
        with (
            patch.object(
                plugin,
                "get_accelerator",
                return_value={
                    "AcceleratorArn": "arn:accelerator",
                    "Enabled": True,
                    "Status": "IN_PROGRESS",
                },
            ),
            patch.object(plugin, "wait_for_accelerator"),
            patch.object(plugin, "get_accelerator_by_arn", return_value=None),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)

        self.assertEqual(raised.exception.values, {"changed": True, "state": "absent"})
        client.delete_accelerator.assert_not_called()

    def test_module_contract(self):
        assert_module_contract(self, plugin)

    def test_main_defers_sdk_validation_until_an_api_is_needed(self):
        endpoint_group = {
            "endpoint_configurations": None,
            "endpoint_group_region": "us-east-1",
            "health_check_interval_seconds": None,
            "health_check_path": None,
            "health_check_port": None,
            "health_check_protocol": None,
            "port_overrides": None,
            "threshold_count": None,
            "traffic_dial_percentage": None,
        }
        module = Mock(
            params={
                "arn": None,
                "idempotency_token": None,
                "ip_addresses": None,
                "listeners": [
                    {
                        "endpoint_groups": [endpoint_group],
                        "port_ranges": [{"from_port": 443, "to_port": 443}],
                        "protocol": "TCP",
                    }
                ],
                "name": "example",
                "purge_endpoint_groups": True,
                "purge_listeners": True,
                "purge_tags": True,
                "state": "present",
                "tags": {},
            },
            client=Mock(return_value=Mock()),
        )
        require_client_methods = Mock()
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "ensure_present"),
            patch.object(plugin, "require_client_methods", require_client_methods),
            patch.object(plugin, "require_positive_wait_bounds"),
            patch.object(plugin, "require_valid_tags"),
        ):
            plugin.main()

        require_client_methods.assert_not_called()

    def test_sdk_validation_checks_endpoint_configuration_parameters(self):
        request = {
            "EndpointConfigurations": [
                {
                    "AttachmentArn": "arn:attachment",
                    "EndpointId": "endpoint-1",
                    "Weight": 128,
                }
            ]
        }
        shape = Mock()
        shape.input_shape.members = {
            "EndpointConfigurations": Mock(member=Mock(members={"EndpointId": Mock(), "Weight": Mock()}))
        }
        client = Mock()
        client.meta.service_model.operation_model.return_value = shape
        module = Mock()
        plugin.require_endpoint_configuration_parameters(
            module,
            client,
            "create_endpoint_group",
            "CreateEndpointGroup",
            request,
        )

        self.assertTrue(
            any(
                "EndpointConfigurations parameter AttachmentArn" in call.kwargs["msg"]
                for call in module.fail_json.call_args_list
            )
        )

    def test_ip_addresses_can_be_cleared(self):
        module = FakeModule(
            {
                "enabled": True,
                "ip_address_type": "IPV4",
                "ip_addresses": [],
                "listeners": None,
                "name": "example",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            },
            check_mode=True,
        )
        current = {
            "AcceleratorArn": "arn:example",
            "Enabled": True,
            "IpAddressType": "IPV4",
            "IpSets": [{"IpAddresses": ["203.0.113.1"]}],
            "Name": "example",
        }
        with (
            patch.object(plugin, "get_accelerator", return_value=current),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            raised.exception.values["accelerator"]["ip_sets"],
            [{"ip_addresses": []}],
        )

    def test_missing_explicit_arn_is_not_replaced_with_an_unselectable_resource(self):
        module = FakeModule(
            {
                "arn": "arn:missing",
                "enabled": True,
                "ip_address_type": "IPV4",
                "ip_addresses": None,
                "listeners": None,
                "name": "example",
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "get_accelerator", return_value=None),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertIn("does not exist", raised.exception.values["msg"])

    def test_update_waits_for_deployment_and_rechecks_desired_state(self):
        client = Mock()
        module = FakeModule(
            {
                "enabled": True,
                "ip_address_type": "IPV4",
                "ip_addresses": None,
                "listeners": None,
                "name": "example",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            }
        )
        transitioning = {
            "AcceleratorArn": "arn:accelerator",
            "Enabled": False,
            "IpAddressType": "IPV4",
            "Name": "example",
            "Status": "IN_PROGRESS",
        }
        deployed = dict(transitioning, Enabled=True, Status="DEPLOYED")
        with (
            patch.object(plugin, "get_accelerator", side_effect=[transitioning, deployed]),
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        wait_for_accelerator.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed")
        self.assertFalse(raised.exception.values["changed"])
        client.update_accelerator.assert_not_called()

    def test_port_ranges_are_normalized_before_comparison(self):
        self.assertEqual(
            plugin.normalized_port_ranges(
                [
                    {"from_port": 443, "to_port": 443, "ignored": True},
                    {"from_port": 80, "to_port": 81},
                ]
            ),
            [
                {"from_port": 80, "to_port": 81},
                {"from_port": 443, "to_port": 443},
            ],
        )

    def test_endpoint_group_comparison_ignores_unmanaged_fields(self):
        current = {
            "endpoint_descriptions": [
                {
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                    "client_ip_preservation_enabled": True,
                }
            ],
            "health_check_port": 443,
            "port_overrides": [{"listener_port": 80, "endpoint_port": 8080}],
        }
        desired = {
            "endpoint_configurations": [
                {
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                    "client_ip_preservation_enabled": None,
                }
            ],
            "endpoint_group_region": "us-east-1",
            "health_check_interval_seconds": None,
            "health_check_path": None,
            "health_check_port": 443,
            "health_check_protocol": None,
            "port_overrides": [{"listener_port": 80, "endpoint_port": 8080}],
            "threshold_count": None,
            "traffic_dial_percentage": None,
        }

        self.assertFalse(plugin.endpoint_group_requires_update(current, desired))
        desired["health_check_port"] = 80
        self.assertTrue(plugin.endpoint_group_requires_update(current, desired))

    def test_endpoint_group_attachment_change_requires_update(self):
        current = {
            "endpoint_descriptions": [
                {
                    "attachment_arn": "arn:old",
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                }
            ]
        }
        desired = {
            "endpoint_configurations": [
                {
                    "attachment_arn": "arn:new",
                    "client_ip_preservation_enabled": None,
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                }
            ],
            "endpoint_group_region": "us-east-1",
            "health_check_interval_seconds": None,
            "health_check_path": None,
            "health_check_port": None,
            "health_check_protocol": None,
            "port_overrides": None,
            "threshold_count": None,
            "traffic_dial_percentage": None,
        }
        self.assertTrue(plugin.endpoint_group_requires_update(current, desired))
        self.assertEqual(
            plugin.predicted_endpoint_group(current, desired)["endpoint_descriptions"][0]["attachment_arn"],
            "arn:new",
        )

    def test_listener_reconciliation_reuses_protocol_listener_for_update(self):
        current = [
            {
                "client_affinity": "NONE",
                "listener_arn": "arn:listener",
                "port_ranges": [{"from_port": 80, "to_port": 80}],
                "protocol": "TCP",
            }
        ]
        module = Mock(
            params={
                "listeners": [
                    {
                        "client_affinity": "SOURCE_IP",
                        "endpoint_groups": None,
                        "port_ranges": [{"from_port": 443, "to_port": 443}],
                        "protocol": "TCP",
                    }
                ],
                "purge_listeners": True,
            }
        )

        matched, updates, creates, deletes = plugin.reconcile_listeners(module, current)

        self.assertEqual(matched, [])
        self.assertEqual(updates[0][0], current[0])
        self.assertEqual(updates[0][1]["port_ranges"], [{"from_port": 443, "to_port": 443}])
        self.assertEqual(creates, [])
        self.assertEqual(deletes, [])

    def test_provider_limits_are_rejected(self):
        cases = [
            (
                {"name": "n" * 256, "ip_addresses": None, "listeners": None},
                "name must contain at most 255 characters",
            ),
            (
                {
                    "idempotency_token": "t" * 256,
                    "ip_addresses": None,
                    "listeners": None,
                },
                "idempotency_token must contain at most 255 characters",
            ),
            (
                {"ip_addresses": ["192.0.2.1"] * 3, "listeners": None},
                "ip_addresses must contain at most 2 entries",
            ),
            (
                {"ip_addresses": ["a" * 46], "listeners": None},
                "ip_addresses entries must contain at most 45 characters",
            ),
            (
                {"ip_addresses": ["not-an-ip"], "listeners": None},
                "ip_addresses entries must be valid IPv4 addresses: not-an-ip",
            ),
            (
                {"ip_addresses": ["192.0.2.1"] * 2, "listeners": None},
                "ip_addresses entries must be unique",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [
                        {
                            "port_ranges": [{"from_port": 1, "to_port": 1}] * 11,
                        }
                    ],
                },
                "listeners entries allow at most 10 port_ranges entries",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [{"port_ranges": []}],
                },
                "listeners entries require at least one port_ranges entry",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [
                        {
                            "endpoint_groups": [{"endpoint_group_region": f"region-{index}"}],
                            "port_ranges": [{"from_port": index + 1, "to_port": index + 1}],
                        }
                        for index in range(43)
                    ],
                },
                "listeners must contain at most 42 endpoint groups in total",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [{"port_ranges": [{"from_port": 0, "to_port": 443}]}],
                },
                "port_ranges entries must be between 1 and 65535",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [{"port_ranges": [{"from_port": 443, "to_port": 80}]}],
                },
                "port_ranges entries require from_port to be less than or equal to to_port",
            ),
            (
                {
                    "ip_addresses": None,
                    "listeners": [
                        {
                            "port_ranges": [
                                {"from_port": 80, "to_port": 90},
                                {"from_port": 90, "to_port": 100},
                            ]
                        }
                    ],
                },
                "listeners port_ranges entries must not overlap",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_listener_port_ranges_must_not_overlap_across_listeners(self):
        assert_module_rejects(
            self,
            plugin,
            {
                "ip_addresses": None,
                "listeners": [
                    {
                        "port_ranges": [{"from_port": 80, "to_port": 90}],
                        "protocol": "TCP",
                    },
                    {
                        "port_ranges": [{"from_port": 90, "to_port": 100}],
                        "protocol": "TCP",
                    },
                ],
            },
            "listeners port_ranges entries must not overlap",
        )

    def test_endpoint_groups_reject_duplicate_regions_and_endpoints(self):
        endpoint = {
            "attachment_arn": None,
            "client_ip_preservation_enabled": None,
            "endpoint_id": "endpoint-1",
            "weight": 128,
        }
        base = {
            "endpoint_configurations": [endpoint],
            "endpoint_group_region": "us-east-1",
        }
        cases = [
            (
                [base, base],
                "Duplicate endpoint group region us-east-1 in endpoint_groups",
            ),
            (
                [dict(base, endpoint_configurations=[endpoint, endpoint])],
                "Duplicate endpoint endpoint-1 in endpoint group us-east-1 endpoint_configurations",
            ),
        ]
        for endpoint_groups, message in cases:
            params = {
                "ip_addresses": None,
                "listeners": [
                    {
                        "endpoint_groups": endpoint_groups,
                        "port_ranges": [{"from_port": 443, "to_port": 443}],
                        "protocol": "TCP",
                    }
                ],
            }
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_endpoint_group_provider_limits_are_rejected(self):
        base = {
            "endpoint_configurations": [],
            "endpoint_group_region": "us-east-1",
            "health_check_port": None,
            "port_overrides": [],
            "threshold_count": None,
            "traffic_dial_percentage": None,
        }
        cases = [
            (
                dict(base, endpoint_group_region="r" * 256),
                "endpoint_group_region must contain at most 255 characters",
            ),
            (
                dict(base, health_check_path="not-a-path"),
                "Endpoint group us-east-1 health_check_path must be a valid path of at most 255 characters",
            ),
            (
                dict(base, health_check_path=r"/invalid\path"),
                "Endpoint group us-east-1 health_check_path must be a valid path of at most 255 characters",
            ),
            (
                dict(base, endpoint_configurations=[{}] * 11),
                "Endpoint group us-east-1 endpoint_configurations must contain at most 10 entries",
            ),
            (
                dict(base, port_overrides=[{}] * 11),
                "Endpoint group us-east-1 port_overrides must contain at most 10 entries",
            ),
            (
                dict(base, health_check_port=0),
                "Endpoint group us-east-1 health_check_port must be between 1 and 65535",
            ),
            (
                dict(base, threshold_count=11),
                "Endpoint group us-east-1 threshold_count must be between 1 and 10",
            ),
            (
                dict(base, traffic_dial_percentage=101),
                "Endpoint group us-east-1 traffic_dial_percentage must be between 0 and 100",
            ),
            (
                dict(
                    base,
                    endpoint_configurations=[{"endpoint_id": "endpoint-1", "weight": 256}],
                ),
                "Endpoint group us-east-1 endpoint_configurations weight must be between 0 and 255",
            ),
            (
                dict(
                    base,
                    endpoint_configurations=[{"endpoint_id": "e" * 256, "weight": 128}],
                ),
                "Endpoint group us-east-1 endpoint IDs and attachment ARNs must contain at most 255 characters",
            ),
            (
                dict(
                    base,
                    port_overrides=[{"endpoint_port": 443, "listener_port": 0}],
                ),
                "Endpoint group us-east-1 port_overrides entries must be between 1 and 65535",
            ),
            (
                dict(
                    base,
                    port_overrides=[
                        {"endpoint_port": 8443, "listener_port": 443},
                        {"endpoint_port": 9443, "listener_port": 443},
                    ],
                ),
                "Endpoint group us-east-1 port_overrides listener_port values must be unique",
            ),
        ]
        for endpoint_group, message in cases:
            params = {
                "ip_addresses": None,
                "listeners": [
                    {
                        "endpoint_groups": [endpoint_group],
                        "port_ranges": [{"from_port": 443, "to_port": 443}],
                    }
                ],
            }
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_endpoint_group_update_sends_changed_attachment(self):
        client = Mock()
        client.update_endpoint_group.return_value = {
            "EndpointGroup": {
                "EndpointGroupArn": "arn:group",
                "EndpointGroupRegion": "us-east-1",
            }
        }
        module = FakeModule({"purge_endpoint_groups": False})
        desired = {
            "endpoint_configurations": [
                {
                    "attachment_arn": "arn:new",
                    "client_ip_preservation_enabled": None,
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                }
            ],
            "endpoint_group_region": "us-east-1",
            "health_check_interval_seconds": None,
            "health_check_path": None,
            "health_check_port": None,
            "health_check_protocol": None,
            "port_overrides": None,
            "threshold_count": None,
            "traffic_dial_percentage": None,
        }
        current = {
            "endpoint_descriptions": [
                {
                    "attachment_arn": "arn:old",
                    "endpoint_id": "endpoint-1",
                    "weight": 128,
                }
            ],
            "endpoint_group_arn": "arn:group",
            "endpoint_group_region": "us-east-1",
        }
        with (
            patch.object(plugin, "get_endpoint_groups", return_value=[current]),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "require_endpoint_configuration_parameters"),
        ):
            changed, groups = plugin.ensure_endpoint_groups(client, module, "arn:listener", [desired])
        require.assert_called_once_with(
            module,
            client,
            "Global Accelerator",
            {
                "update_endpoint_group": (
                    "EndpointConfigurations",
                    "EndpointGroupArn",
                )
            },
        )
        self.assertTrue(changed)
        self.assertEqual(groups[0]["endpoint_group_arn"], "arn:group")
        self.assertEqual(
            client.update_endpoint_group.call_args.kwargs["EndpointConfigurations"],
            [
                {
                    "AttachmentArn": "arn:new",
                    "EndpointId": "endpoint-1",
                    "Weight": 128,
                }
            ],
        )

    def test_absent_waits_for_prerequisites_when_wait_is_disabled(self):
        client = Mock()
        module = FakeModule({"wait": False})

        with (
            patch.object(
                plugin,
                "get_accelerator",
                return_value={"AcceleratorArn": "arn:accelerator", "Enabled": True},
            ),
            patch.object(
                plugin,
                "get_listeners",
                return_value=[{"listener_arn": "arn:listener"}],
            ),
            patch.object(plugin, "delete_listener") as delete_listener,
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            patch.object(plugin, "require_client_methods"),
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_absent(client, module)

        delete_listener.assert_called_once_with(client, module, "arn:accelerator", "arn:listener")
        self.assertEqual(wait_for_accelerator.call_count, 2)
        for call in wait_for_accelerator.call_args_list:
            self.assertEqual(
                call.args,
                (client, module, "arn:accelerator", "accelerator_deployed"),
            )
        client.delete_accelerator.assert_called_once_with(AcceleratorArn="arn:accelerator", aws_retry=True)

    def test_listener_deletion_waits_for_endpoint_group_deletion(self):
        client = Mock()
        module = FakeModule({})
        with (
            patch.object(
                plugin,
                "get_endpoint_groups",
                return_value=[{"endpoint_group_arn": "arn:group"}],
            ),
            patch.object(plugin, "delete_endpoint_group") as delete_endpoint_group,
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            patch.object(plugin, "require_client_methods") as require,
        ):
            plugin.delete_listener(client, module, "arn:accelerator", "arn:listener")

        delete_endpoint_group.assert_called_once_with(client, module, "arn:group")
        wait_for_accelerator.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed")
        client.delete_listener.assert_called_once_with(ListenerArn="arn:listener", aws_retry=True)
        require.assert_called_once_with(
            module,
            client,
            "Global Accelerator",
            {"delete_listener": ("ListenerArn",)},
        )

    def test_listener_creation_waits_before_endpoint_groups(self):
        client = Mock()
        client.create_listener.return_value = {"Listener": {"ListenerArn": "arn:listener"}}
        desired = {
            "client_affinity": "NONE",
            "endpoint_groups": [{"endpoint_group_region": "us-east-1"}],
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
        module = FakeModule({"purge_listeners": True})
        with (
            patch.object(
                plugin,
                "reconcile_listeners",
                return_value=([], [], [desired], []),
            ),
            patch.object(plugin, "get_listeners", return_value=[]),
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            patch.object(plugin, "ensure_endpoint_groups", return_value=(False, [])),
            patch.object(plugin, "require_client_methods"),
        ):
            plugin.ensure_listeners(client, module, "arn:accelerator")

        wait_for_accelerator.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed")

    def test_listener_replacement_retries_after_freeing_quota(self):
        client = Mock()
        client.create_listener.side_effect = [
            plugin.ClientError(
                {"Error": {"Code": "LimitExceededException", "Message": "full"}},
                "CreateListener",
            ),
            {"Listener": {"ListenerArn": "arn:new"}},
        ]
        desired = {
            "client_affinity": "NONE",
            "endpoint_groups": None,
            "port_ranges": [{"from_port": 443, "to_port": 443}],
            "protocol": "TCP",
        }
        current = {"listener_arn": "arn:old"}
        module = FakeModule({"purge_listeners": True})
        with (
            patch.object(
                plugin,
                "reconcile_listeners",
                return_value=([], [], [desired], [current]),
            ),
            patch.object(plugin, "get_listeners", return_value=[current]),
            patch.object(plugin, "delete_listener") as delete_listener,
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            patch.object(plugin, "require_client_methods"),
        ):
            changed, listeners = plugin.ensure_listeners(client, module, "arn:accelerator")

        self.assertTrue(changed)
        self.assertEqual(listeners[0]["listener_arn"], "arn:new")
        self.assertEqual(client.create_listener.call_count, 2)
        delete_listener.assert_called_once_with(client, module, "arn:accelerator", "arn:old")
        wait_for_accelerator.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed")

    def test_accelerator_creation_waits_before_listeners(self):
        client = Mock()
        client.create_accelerator.return_value = {
            "Accelerator": {
                "AcceleratorArn": "arn:accelerator",
                "Name": "example",
            }
        }
        module = FakeModule(
            {
                "enabled": True,
                "idempotency_token": None,
                "ip_addresses": None,
                "ip_address_type": "IPV4",
                "listeners": [{}],
                "name": "example",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            }
        )
        with (
            patch.object(plugin, "get_accelerator", return_value=None),
            patch.object(plugin, "wait_for_accelerator") as wait_for_accelerator,
            patch.object(plugin, "ensure_listeners", return_value=(True, [])),
            patch.object(plugin, "require_client_methods") as require,
            self.assertRaises(ModuleExit),
        ):
            plugin.ensure_present(client, module)

        wait_for_accelerator.assert_called_once_with(client, module, "arn:accelerator", "accelerator_deployed")
        self.assertEqual(
            require.call_args.args[3],
            {
                "create_accelerator": (
                    "Enabled",
                    "IdempotencyToken",
                    "IpAddressType",
                    "Name",
                )
            },
        )
