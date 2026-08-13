from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    glue_connection_info as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
)


class GlueConnectionInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["required_by"] == {
            "apply_override_for_compute_environment": ["name"]
        }

    def test_named_connection_only_gates_used_parameters(self):
        client = Mock(
            get_connection=Mock(return_value={"Connection": {"Name": "main"}})
        )
        module = FakeModule(
            {
                "apply_override_for_compute_environment": None,
                "catalog_id": "catalog",
                "filters": None,
                "hide_password": True,
                "name": "main",
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        require_methods.assert_called_once_with(
            module,
            client,
            "AWS Glue",
            {
                "get_connection": (
                    "CatalogId",
                    "HidePassword",
                    "Name",
                )
            },
        )
        client.get_connection.assert_called_once_with(
            CatalogId="catalog",
            HidePassword=True,
            Name="main",
            aws_retry=True,
        )

    def test_connection_list_only_gates_used_parameters(self):
        client = Mock(get_connections=Mock(return_value={"ConnectionList": []}))
        client.can_paginate.return_value = False
        module = FakeModule(
            {
                "apply_override_for_compute_environment": None,
                "catalog_id": None,
                "filters": None,
                "hide_password": True,
                "name": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "query_list", return_value=[]),
            patch.object(plugin, "require_client_methods") as require_methods,
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        require_methods.assert_called_once_with(
            module,
            client,
            "AWS Glue",
            {"get_connections": ("HidePassword", "MaxResults", "NextToken")},
        )
