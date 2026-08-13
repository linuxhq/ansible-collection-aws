from unittest import TestCase
from unittest.mock import Mock, patch

from ansible_collections.linuxhq.aws.plugins.modules import (
    acm_certificate_request as plugin,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


class AcmCertificateRequestTests(TestCase):
    def test_sdk_validation_matches_used_parameters(self):
        client = Mock()
        client.request_certificate.return_value = {"CertificateArn": "arn:new"}
        module = FakeModule(
            {
                "domain_name": "example.com",
                "idempotency_token": None,
                "purge_tags": True,
                "subject_alternative_names": ["www.example.com"],
                "tags": {"Name": "example"},
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods") as require,
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()

        self.assertEqual(require.call_count, 2)
        self.assertEqual(
            require.call_args_list[0].args[3],
            {
                "list_certificates": (
                    "CertificateStatuses",
                    "MaxItems",
                    "NextToken",
                ),
            },
        )
        self.assertEqual(
            require.call_args_list[1].args[3],
            {
                "request_certificate": (
                    "DomainName",
                    "IdempotencyToken",
                    "ValidationMethod",
                    "SubjectAlternativeNames",
                    "Tags",
                ),
            },
        )

    def test_certificate_disappearing_during_describe_is_replaced(self):
        client = Mock()
        client.describe_certificate.side_effect = plugin.ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
            "DescribeCertificate",
        )
        client.request_certificate.return_value = {"CertificateArn": "arn:new"}
        module = FakeModule(
            {
                "domain_name": "example.com",
                "idempotency_token": None,
                "purge_tags": True,
                "subject_alternative_names": [],
                "tags": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(
                plugin,
                "query_list",
                return_value=[
                    {
                        "CertificateArn": "arn:gone",
                        "DomainName": "example.com",
                    }
                ],
            ),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()

        self.assertTrue(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["certificate_arn"], "arn:new")

    def test_module_contract(self):
        options = assert_module_contract(self, plugin)
        assert (
            options["argument_spec"]["subject_alternative_names"]["elements"] == "str"
        )

    def test_rejects_invalid_idempotency_token_before_api_calls(self):
        module = FakeModule(
            {
                "domain_name": "example.com",
                "idempotency_token": "contains-hyphens",
                "purge_tags": True,
                "subject_alternative_names": [],
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("idempotency_token", raised.exception.values["msg"])

    def test_rejects_too_many_subject_alternative_names(self):
        module = FakeModule(
            {
                "domain_name": "example.com",
                "idempotency_token": None,
                "purge_tags": True,
                "subject_alternative_names": [
                    f"name-{index}.example.com" for index in range(100)
                ],
                "tags": None,
            }
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            self.assertRaises(ModuleFail) as raised,
        ):
            plugin.main()
        self.assertIn("at most 99", raised.exception.values["msg"])

    def test_reuses_the_newest_matching_dns_certificate(self):
        client = Mock()
        client.describe_certificate.side_effect = [
            {
                "Certificate": {
                    "CertificateArn": "arn:old",
                    "CreatedAt": 1,
                    "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
                    "SubjectAlternativeNames": ["example.com", "WWW.EXAMPLE.COM"],
                    "Type": "AMAZON_ISSUED",
                }
            },
            {
                "Certificate": {
                    "CertificateArn": "arn:new",
                    "CreatedAt": 2,
                    "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
                    "SubjectAlternativeNames": ["EXAMPLE.COM", "www.example.com"],
                    "Type": "AMAZON_ISSUED",
                }
            },
        ]
        module = FakeModule(
            {
                "domain_name": "Example.COM",
                "idempotency_token": None,
                "purge_tags": True,
                "subject_alternative_names": ["www.example.com"],
                "tags": None,
            },
            client=client,
        )
        summaries = [
            {"CertificateArn": "arn:old", "DomainName": "example.com"},
            {"CertificateArn": "arn:new", "DomainName": "EXAMPLE.COM"},
        ]
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=summaries),
            self.assertRaises(ModuleExit) as raised,
        ):
            plugin.main()
        self.assertFalse(raised.exception.values["changed"])
        self.assertEqual(raised.exception.values["certificate_arn"], "arn:new")
        client.request_certificate.assert_not_called()

    def test_generated_idempotency_token_is_stable_for_normalized_names(self):
        client = Mock()
        client.request_certificate.return_value = {"CertificateArn": "arn:new"}
        module = FakeModule(
            {
                "domain_name": "Example.COM",
                "idempotency_token": None,
                "purge_tags": True,
                "subject_alternative_names": [
                    "WWW.example.com",
                    "api.EXAMPLE.com",
                    "www.EXAMPLE.com",
                    "EXAMPLE.com",
                ],
                "tags": None,
            },
            client=client,
        )
        with (
            patch.object(plugin, "AnsibleAWSModule", return_value=module),
            patch.object(plugin, "require_client_methods"),
            patch.object(plugin, "query_list", return_value=[]),
            self.assertRaises(ModuleExit),
        ):
            plugin.main()
        self.assertEqual(
            client.request_certificate.call_args.kwargs["IdempotencyToken"],
            "e113b629356ead495e5f4cfb72dfd792",
        )
        self.assertEqual(
            client.request_certificate.call_args.kwargs["SubjectAlternativeNames"],
            ["www.example.com", "api.example.com"],
        )
