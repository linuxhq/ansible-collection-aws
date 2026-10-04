from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import acm_certificate_request as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)


def test_sdk_validation_matches_used_parameters():
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
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert require.call_count == 2
    assert require.call_args_list[0].args[3] == {
        "list_certificates": (
            "CertificateStatuses",
            "Includes",
            "MaxItems",
            "NextToken",
        ),
    }
    assert query.call_args.kwargs["Includes"] == {
        "keyTypes": [
            "RSA_1024",
            "RSA_2048",
            "RSA_3072",
            "RSA_4096",
            "EC_prime256v1",
            "EC_secp384r1",
            "EC_secp521r1",
        ]
    }
    assert require.call_args_list[1].args[3] == {
        "request_certificate": (
            "DomainName",
            "IdempotencyToken",
            "ValidationMethod",
            "SubjectAlternativeNames",
            "Tags",
        ),
    }


def test_certificate_disappearing_during_describe_is_replaced():
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
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    assert raised.value.values["certificate_arn"] == "arn:new"


def test_module_contract():
    options = assert_module_contract(plugin)
    assert options["argument_spec"]["subject_alternative_names"]["elements"] == "str"
    assert options["argument_spec"]["tags"]["aliases"] == ["resource_tags"]


def test_rejects_invalid_idempotency_token_before_api_calls():
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
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "idempotency_token" in raised.value.values["msg"]


def test_rejects_too_many_subject_alternative_names():
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": [f"name-{index}.example.com" for index in range(100)],
            "tags": None,
        }
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "at most 99" in raised.value.values["msg"]


def test_reuses_the_newest_matching_dns_certificate():
    client = Mock()
    client.describe_certificate.side_effect = [
        {
            "Certificate": {
                "CertificateArn": "arn:old",
                "CreatedAt": 1,
                "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
                "Status": "ISSUED",
                "SubjectAlternativeNames": ["example.com", "WWW.EXAMPLE.COM"],
                "Type": "AMAZON_ISSUED",
            }
        },
        {
            "Certificate": {
                "CertificateArn": "arn:new",
                "CreatedAt": 2,
                "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
                "Status": "PENDING_VALIDATION",
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
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert not raised.value.values["changed"]
    assert raised.value.values["certificate_arn"] == "arn:new"
    client.request_certificate.assert_not_called()


def test_replaces_candidate_that_is_no_longer_pending_or_issued():
    client = Mock()
    client.describe_certificate.return_value = {
        "Certificate": {
            "CertificateArn": "arn:expired",
            "CreatedAt": 1,
            "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
            "Status": "EXPIRED",
            "SubjectAlternativeNames": ["example.com"],
            "Type": "AMAZON_ISSUED",
        }
    }
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
                    "CertificateArn": "arn:expired",
                    "DomainName": "example.com",
                }
            ],
        ),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"]
    assert raised.value.values["certificate_arn"] == "arn:new"


def test_rejects_candidate_with_missing_described_status():
    client = Mock()
    client.describe_certificate.return_value = {"Certificate": {}}
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
                    "CertificateArn": "arn:missing-status",
                    "DomainName": "example.com",
                }
            ],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "did not return a status" in raised.value.values["msg"]
    client.request_certificate.assert_not_called()


def test_rejects_matching_certificate_summary_without_arn():
    client = Mock()
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
        patch.object(plugin, "query_list", return_value=[{"CertificateArn": 7, "DomainName": "example.com"}]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "invalid matching certificate summary" in raised.value.values["msg"]
    client.request_certificate.assert_not_called()


def test_rejects_malformed_certificate_summaries():
    client = Mock()
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
            return_value=[None, {}, {"DomainName": 7}, {"DomainName": "other.example.com"}],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "invalid certificate summary" in raised.value.values["msg"]
    client.request_certificate.assert_not_called()
    client.describe_certificate.assert_not_called()


def test_rejects_matching_certificate_without_creation_time():
    client = Mock()
    client.describe_certificate.return_value = {
        "Certificate": {
            "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
            "Status": "ISSUED",
            "SubjectAlternativeNames": ["example.com"],
            "Type": "AMAZON_ISSUED",
        }
    }
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
            return_value=[{"CertificateArn": "arn:missing-created-at", "DomainName": "example.com"}],
        ),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert "did not return a creation time" in raised.value.values["msg"]
    client.request_certificate.assert_not_called()


def test_generated_idempotency_token_is_stable_for_normalized_names():
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
        pytest.raises(ModuleExit),
    ):
        plugin.main()

    assert client.request_certificate.call_args.kwargs["IdempotencyToken"] == "e113b629356ead495e5f4cfb72dfd792"
    assert client.request_certificate.call_args.kwargs["SubjectAlternativeNames"] == [
        "www.example.com",
        "api.example.com",
    ]


def issued_certificate(arn, **overrides):
    return {
        "Certificate": dict(
            {
                "CertificateArn": arn,
                "CreatedAt": 1,
                "DomainValidationOptions": [{"ValidationMethod": "DNS"}],
                "Status": "ISSUED",
                "SubjectAlternativeNames": ["example.com"],
                "Type": "AMAZON_ISSUED",
            },
            **overrides,
        )
    }


def run_request(client, summaries):
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": None,
            "tags": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=summaries),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    return result.value.values


def test_summaries_rule_out_certificates_without_describing_them():
    client = Mock()
    client.describe_certificate.return_value = issued_certificate("arn:match")
    summaries = [
        {"CertificateArn": "arn:imported", "DomainName": "example.com", "Type": "IMPORTED"},
        {"CertificateArn": "arn:cloudfront", "DomainName": "example.com", "ManagedBy": "CLOUDFRONT"},
        {
            "CertificateArn": "arn:other-names",
            "DomainName": "example.com",
            "HasAdditionalSubjectAlternativeNames": False,
            "SubjectAlternativeNameSummaries": ["example.com", "www.example.com"],
        },
        {
            "CertificateArn": "arn:match",
            "DomainName": "example.com",
            "HasAdditionalSubjectAlternativeNames": False,
            "SubjectAlternativeNameSummaries": ["EXAMPLE.COM"],
            "Type": "AMAZON_ISSUED",
        },
    ]

    result = run_request(client, summaries)

    assert result["certificate_arn"] == "arn:match"
    client.describe_certificate.assert_called_once_with(CertificateArn="arn:match", aws_retry=True)
    client.request_certificate.assert_not_called()


def test_truncated_summary_names_are_described():
    client = Mock()
    client.describe_certificate.return_value = issued_certificate("arn:truncated")
    summaries = [
        {
            "CertificateArn": "arn:truncated",
            "DomainName": "example.com",
            "HasAdditionalSubjectAlternativeNames": True,
            "SubjectAlternativeNameSummaries": ["other.example.com"],
        }
    ]

    result = run_request(client, summaries)

    assert result["certificate_arn"] == "arn:truncated"
    client.describe_certificate.assert_called_once()


def test_service_managed_certificate_is_not_reused():
    client = Mock()
    client.describe_certificate.return_value = issued_certificate("arn:managed", ManagedBy="CLOUDFRONT")
    client.request_certificate.return_value = {"CertificateArn": "arn:new"}

    result = run_request(client, [{"CertificateArn": "arn:managed", "DomainName": "example.com"}])

    assert result["changed"] is True
    assert result["certificate_arn"] == "arn:new"
