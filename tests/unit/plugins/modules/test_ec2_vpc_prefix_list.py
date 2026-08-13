from unittest import TestCase
from unittest.mock import Mock, call, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    ec2_vpc_prefix_list as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class Ec2VpcPrefixListTests(TestCase):
    def test_sdk_validation_starts_with_lookup_only(self):
        module = Mock(
            params={
                "address_family": "IPv4",
                "entries": [{"cidr": "10.0.0.0/8"}],
                "name": "main",
                "purge_tags": True,
                "state": "present",
                "tags": {},
                "wait": False,
                "wait_delay": 1,
                "wait_timeout": 60,
            },
            client=Mock(return_value=Mock()),
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "ensure_present"),
        ):
            plugin.main()

        require.assert_called_once_with(
            module,
            module.client.return_value,
            "EC2",
            {
                "describe_managed_prefix_lists": (
                    "Filters",
                    "MaxResults",
                    "NextToken",
                )
            },
        )

    def test_delete_tolerates_prefix_list_disappearing(self):
        client = Mock()
        client.delete_managed_prefix_list.side_effect = plugin.ClientError(
            {"Error": {"Code": "InvalidPrefixListID.NotFound", "Message": "gone"}},
            "DeleteManagedPrefixList",
        )
        module = FakeModule({"name": "main", "wait": True})
        with (
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "wait_for_prefix_list_state") as wait,
        ):
            plugin.delete_prefix_list(client, module, "pl-1")
        require.assert_called_once_with(
            module,
            client,
            "EC2",
            {"delete_managed_prefix_list": ("PrefixListId",)},
        )
        wait.assert_not_called()

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_if"] == [("state", "present", ["entries"])]

    def test_entries_are_normalized_and_sorted(self):
        assert plugin.comparable_entries(
            [
                {"Cidr": "192.0.2.0/24", "Description": None},
                {"Cidr": "10.0.0.0/8", "Description": "private"},
            ]
        ) == [
            {"cidr": "10.0.0.0/8", "description": "private"},
            {"cidr": "192.0.2.0/24"},
        ]

    def test_entry_changes_include_current_prefix_list_version(self):
        client = Mock()
        module = Mock(params={"name": "main"})
        with patch.object(plugin, "require_client_methods") as require:
            plugin.modify_prefix_list(
                client,
                module,
                {"PrefixListId": "pl-1", "Version": 3},
                add_entries=[{"cidr": "192.0.2.0/24"}],
            )

        require.assert_called_once_with(
            module,
            client,
            "EC2",
            {
                "modify_managed_prefix_list": (
                    "PrefixListId",
                    "CurrentVersion",
                    "AddEntries",
                )
            },
        )
        client.modify_managed_prefix_list.assert_called_once_with(
            AddEntries=[{"Cidr": "192.0.2.0/24"}],
            CurrentVersion=3,
            PrefixListId="pl-1",
            aws_retry=True,
        )

    def test_create_without_wait_returns_the_create_response(self):
        client = Mock(
            create_managed_prefix_list=Mock(
                return_value={"PrefixList": {"PrefixListId": "pl-new"}}
            )
        )
        module = FakeModule({"name": "main", "tags": None, "wait": False})
        entries = [{"cidr": "192.0.2.0/24"}]
        with (
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "get_current") as get_current,
        ):
            result = plugin.create_prefix_list(
                client,
                module,
                {
                    "address_family": "IPv4",
                    "max_entries": 1,
                    "prefix_list_name": "main",
                },
                entries,
            )

        require.assert_called_once_with(
            module,
            client,
            "EC2",
            {
                "create_managed_prefix_list": (
                    "AddressFamily",
                    "MaxEntries",
                    "PrefixListName",
                    "Entries",
                )
            },
        )
        self.assertEqual(result, ({"PrefixListId": "pl-new"}, entries))
        get_current.assert_not_called()

    def test_additive_check_mode_preserves_unmanaged_tags(self):
        current = {
            "AddressFamily": "IPv4",
            "MaxEntries": 1,
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "Tags": [
                {"Key": "keep", "Value": "yes"},
                {"Key": "managed", "Value": "old"},
            ],
        }
        entries = [{"Cidr": "10.0.0.0/8"}]
        module = FakeModule(
            {
                "address_family": "IPv4",
                "entries": [{"cidr": "10.0.0.0/8"}],
                "name": "main",
                "purge_tags": False,
                "tags": {"managed": "new"},
                "wait": False,
            },
            check_mode=True,
        )
        with (
            patch.object(plugin, "get_current", return_value=(current, entries)),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(Mock(), module)

        self.assertEqual(
            raised.exception.values["prefix_list"]["tags"],
            {"keep": "yes", "managed": "new"},
        )

    def test_entry_replacement_removes_before_shrinking_and_adding(self):
        client = Mock()
        module = FakeModule(
            {
                "address_family": "IPv4",
                "entries": [{"cidr": "192.0.2.0/24"}],
                "name": "main",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            }
        )
        initial = {
            "AddressFamily": "IPv4",
            "MaxEntries": 2,
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "Version": 1,
        }
        resized = dict(initial, MaxEntries=1, Version=3)
        with (
            patch.object(
                plugin,
                "get_current",
                side_effect=[
                    (initial, [{"Cidr": "10.0.0.0/8"}, {"Cidr": "172.16.0.0/12"}]),
                    (dict(initial, Version=2), []),
                    (resized, []),
                ],
            ),
            patch.object(plugin, "modify_prefix_list") as modify,
            patch.object(plugin, "wait_for_ready_state") as wait_for_ready_state,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(
            modify.call_args_list,
            [
                call(
                    client,
                    module,
                    initial,
                    remove_entries=[
                        {"cidr": "10.0.0.0/8"},
                        {"cidr": "172.16.0.0/12"},
                    ],
                ),
                call(client, module, dict(initial, Version=2), max_entries=1),
                call(
                    client,
                    module,
                    resized,
                    add_entries=[{"cidr": "192.0.2.0/24"}],
                ),
            ],
        )
        self.assertEqual(wait_for_ready_state.call_count, 2)
        self.assertEqual(
            raised.exception.values["prefix_list"]["entries"],
            [{"cidr": "192.0.2.0/24"}],
        )

    def test_present_entries_must_be_nonempty_and_unique(self):
        base = {"address_family": "IPv4", "state": "present", "tags": None}
        cases = [
            (
                dict(base, entries=[]),
                "entries must contain at least one item when state=present",
            ),
            (
                dict(
                    base,
                    entries=[{"cidr": f"10.0.0.{index}/32"} for index in range(101)],
                ),
                "entries must contain at most 100 items",
            ),
            (
                dict(
                    base,
                    entries=[{"cidr": "10.0.0.0/8"}, {"cidr": "10.0.0.0/8"}],
                ),
                "entries[].cidr values must be unique",
            ),
            (
                dict(base, entries=[{"cidr": "not-a-cidr"}]),
                "entries[].cidr must be a valid CIDR: not-a-cidr",
            ),
            (
                dict(base, entries=[{"cidr": "2001:db8::/32"}]),
                "entries[].cidr must match address_family IPv4: 2001:db8::/32",
            ),
            (
                dict(
                    base,
                    entries=[{"cidr": "192.0.2.0/24", "description": "d" * 256}],
                ),
                "entries[].description must contain at most 255 characters",
            ),
        ]
        for params, message in cases:
            with self.subTest(message=message):
                assert_module_rejects(self, plugin, params, message)

    def test_address_family_change_recreates_without_a_useless_modify(self):
        client = Mock()
        module = FakeModule(
            {
                "address_family": "IPv6",
                "entries": [{"cidr": "2001:db8::/32"}],
                "name": "main",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            }
        )
        current = {
            "AddressFamily": "IPv4",
            "MaxEntries": 1,
            "PrefixListId": "pl-old",
            "PrefixListName": "main",
            "Version": 1,
        }
        entries = [{"Cidr": "10.0.0.0/8"}]
        desired_entries = [{"Cidr": "2001:db8::/32"}]
        replacement = dict(current, AddressFamily="IPv6", PrefixListId="pl-new")
        with (
            patch.object(plugin, "get_current", return_value=(current, entries)),
            patch.object(plugin, "delete_prefix_list") as delete,
            patch.object(
                plugin,
                "create_prefix_list",
                return_value=(replacement, desired_entries),
            ) as create,
            patch.object(plugin, "modify_prefix_list") as modify,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        self.assertTrue(raised.exception.values["changed"])
        delete.assert_called_once_with(client, module, "pl-old", always=True)
        create.assert_called_once()
        modify.assert_not_called()

    def test_present_waits_for_an_existing_modification_and_rechecks(self):
        client = Mock()
        module = FakeModule(
            {
                "address_family": "IPv4",
                "entries": [{"cidr": "10.0.0.0/8"}],
                "name": "main",
                "purge_tags": True,
                "tags": None,
                "wait": False,
            }
        )
        transitioning = {
            "AddressFamily": "IPv4",
            "MaxEntries": 2,
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "State": "modify-in-progress",
        }
        ready = dict(transitioning, MaxEntries=1, State="modify-complete")
        with (
            patch.object(
                plugin,
                "get_current",
                side_effect=[
                    (transitioning, [{"Cidr": "10.0.0.0/8"}]),
                    (ready, [{"Cidr": "10.0.0.0/8"}]),
                ],
            ),
            patch.object(plugin, "wait_for_ready_state") as wait_for_ready_state,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_present(client, module)
        wait_for_ready_state.assert_called_once_with(client, module, "pl-1")
        self.assertFalse(raised.exception.values["changed"])
        client.modify_managed_prefix_list.assert_not_called()

    def test_absent_does_not_repeat_an_in_progress_delete(self):
        client = Mock()
        module = FakeModule({"name": "main", "wait": False})
        current = {
            "PrefixListId": "pl-1",
            "PrefixListName": "main",
            "State": "delete-in-progress",
        }
        with (
            patch.object(
                plugin,
                "get_customer_managed_prefix_list_by_name",
                return_value=current,
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.ensure_absent(client, module)
        self.assertFalse(raised.exception.values["changed"])
        client.delete_managed_prefix_list.assert_not_called()

    def test_lookup_ignores_delete_complete_tombstones(self):
        module = FakeModule({"name": "main"})
        active = {
            "OwnerId": "123456789012",
            "PrefixListId": "pl-new",
            "State": "create-complete",
        }
        with patch.object(
            plugin,
            "query_list",
            return_value=[
                {
                    "OwnerId": "123456789012",
                    "PrefixListId": "pl-old",
                    "State": "delete-complete",
                },
                active,
            ],
        ):
            self.assertEqual(
                plugin.get_customer_managed_prefix_list_by_name(Mock(), module),
                active,
            )
