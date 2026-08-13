from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import ses_identity_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    assert_module_contract,
    assert_module_rejects,
)


class SesIdentityInfoTests(TestCase):
    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert options["mutually_exclusive"] == [["identity_type", "name"]]

    def test_named_identity_skips_listing(self):
        sesv2 = Mock(get_email_identity=Mock(return_value={"VerifiedForSendingStatus": True, "ResponseMetadata": {}}))
        module = FakeModule({"identity_type": None, "name": "example.com"})
        module.client = Mock(return_value=sesv2)
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list") as query,
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        query.assert_not_called()
        require_methods.assert_called_once_with(
            module,
            sesv2,
            "SESv2",
            {"get_email_identity": ("EmailIdentity",)},
        )
        self.assertEqual(raised.exception.values["identities"][0]["name"], "example.com")

    def test_empty_name_is_rejected(self):
        assert_module_rejects(
            self,
            plugin,
            {"identity_type": None, "name": ""},
            "name must not be empty",
        )

    def test_listing_requires_pagination_parameters(self):
        ses = Mock()
        sesv2 = Mock()
        module = FakeModule({"identity_type": "Domain", "name": None})
        module.client = Mock(side_effect=[ses, sesv2])
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require_methods,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        require_methods.assert_any_call(
            module,
            ses,
            "SES",
            {"list_identities": ("IdentityType", "MaxItems", "NextToken")},
        )
