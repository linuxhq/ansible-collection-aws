import re
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.modules import acm_certificate_request as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)

# Replayed certificates were created by an earlier request.
EARLIER = datetime.now(timezone.utc) - timedelta(minutes=10)


def created_now():
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def no_sleep():
    with patch.object(plugin.time, "sleep") as sleep:
        yield sleep


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
    assert query.call_args_list[0].kwargs["Includes"] == {
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
            "SubjectAlternativeNames",
            "Tags",
            "ValidationMethod",
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


@pytest.mark.parametrize("check_mode", [True, False])
@pytest.mark.parametrize(
    ("domain_name", "subject_alternative_names", "message"),
    [
        ("", None, "domain_name must not be empty"),
        (" ", None, "domain_name must not be empty"),
        ("example.com", ["www.example.com", ""], "subject_alternative_names must not contain empty entries"),
        ("example.com", [" "], "subject_alternative_names must not contain empty entries"),
    ],
)
def test_rejects_blank_names_before_api_calls(check_mode, domain_name, subject_alternative_names, message):
    # A blank name never matches a certificate, so check mode would predict a request that ACM rejects.
    module = FakeModule(
        {
            "domain_name": domain_name,
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": subject_alternative_names,
            "tags": None,
        },
        check_mode=check_mode,
    )
    module.client = Mock()
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"msg": message}
    module.client.assert_not_called()
    query.assert_not_called()


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


@pytest.mark.parametrize("malformed", [None, {"DomainName": 7}], ids=["not-a-dict", "non-string-domain"])
def test_rejects_malformed_certificate_summaries(malformed):
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
            return_value=[{"CertificateArn": "arn:no-domain"}, malformed, {"DomainName": "other.example.com"}],
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


REQUESTED_NAMES = ["example.com", "www.example.com", "api.example.com"]


def request_new_certificate(idempotency_token=None):
    client = Mock()
    client.request_certificate.return_value = {"CertificateArn": "arn:new"}
    client.describe_certificate.return_value = {
        "Certificate": {
            "CreatedAt": created_now(),
            "Status": "PENDING_VALIDATION",
            "SubjectAlternativeNames": REQUESTED_NAMES,
        }
    }
    module = FakeModule(
        {
            "domain_name": "Example.COM",
            "idempotency_token": idempotency_token,
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

    client.request_certificate.assert_called_once()
    return client.request_certificate.call_args.kwargs


def test_generated_idempotency_token_is_unique_per_request():
    first = request_new_certificate()
    second = request_new_certificate()

    assert re.fullmatch(r"\w{1,32}", first["IdempotencyToken"], flags=re.ASCII)
    assert re.fullmatch(r"\w{1,32}", second["IdempotencyToken"], flags=re.ASCII)
    assert first["IdempotencyToken"] != second["IdempotencyToken"]
    assert first["SubjectAlternativeNames"] == ["www.example.com", "api.example.com"]


def test_supplied_idempotency_token_is_sent_unchanged():
    request = request_new_certificate("Custom_Token_1")

    assert request["IdempotencyToken"] == "Custom_Token_1"


def run_token_request(described, listed=()):
    client = Mock()
    client.request_certificate.return_value = {"CertificateArn": "arn:replayed"}
    if isinstance(described, Exception):
        client.describe_certificate.side_effect = described
    else:
        client.describe_certificate.return_value = {"Certificate": described}

    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": "Token_1",
            "purge_tags": True,
            "subject_alternative_names": ["www.example.com"],
            "tags": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require,
        patch.object(
            plugin,
            "query_list",
            side_effect=lambda *args, **kwargs: (
                list(listed) if kwargs.get("CertificateStatuses") == plugin.CERTIFICATE_STATUSES else []
            ),
        ) as query,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    client.request_certificate.assert_called_once()
    client.describe_certificate.assert_called_with(CertificateArn="arn:replayed", aws_retry=True)
    # Every status is listed before the request.
    assert query.call_args_list[1].kwargs["CertificateStatuses"] == plugin.CERTIFICATE_STATUSES
    assert require.call_args_list[1].args[3]["describe_certificate"] == ("CertificateArn",)
    return raised.value, query


@pytest.mark.parametrize(
    ("described", "reason"),
    [
        # Live: a token and names repeated within the hour return the earlier certificate after it FAILED.
        (
            {"CreatedAt": EARLIER, "Status": "FAILED", "SubjectAlternativeNames": ["example.com", "www.example.com"]},
            "which is FAILED",
        ),
        (
            {"CreatedAt": EARLIER, "Status": "PENDING_VALIDATION", "SubjectAlternativeNames": ["example.com"]},
            "which has other domain names",
        ),
    ],
    ids=["failed", "other-names"],
)
def test_supplied_token_returning_a_certificate_that_cannot_be_reused_fails_without_changes(described, reason):
    result, query = run_token_request(described)

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "msg": (
            "idempotency_token Token_1 was already used to request AWS Certificate Manager certificate arn:replayed, "
            f"{reason}; use a new idempotency_token or omit it"
        ),
        "certificate_arn": "arn:replayed",
    }
    # The certificate listing wait is skipped.
    assert query.call_count == 2


def test_supplied_token_returning_a_usable_certificate_is_reported_as_requested():
    result, _query = run_token_request(
        {
            "CreatedAt": EARLIER,
            "Status": "PENDING_VALIDATION",
            "SubjectAlternativeNames": ["WWW.example.com", "example.com"],
        }
    )

    assert isinstance(result, ModuleExit)
    assert result.values == {"changed": True, "certificate_arn": "arn:replayed"}


@pytest.mark.parametrize(
    "created_at",
    [
        created_now,
        # Clock skew between the managed node and AWS of a few seconds.
        lambda: datetime.now(timezone.utc) - plugin.REQUEST_CLOCK_SKEW + timedelta(seconds=1),
    ],
    ids=["after-request", "within-clock-skew"],
)
@pytest.mark.parametrize("status", ["FAILED", "VALIDATION_TIMED_OUT", "PENDING_VALIDATION"])
def test_supplied_token_certificate_created_by_the_request_is_reported_as_requested(created_at, status):
    # Live: a new certificate went FAILED (ADDITIONAL_VERIFICATION_REQUIRED) 4 seconds after it was requested.
    result, query = run_token_request(
        {
            "CreatedAt": created_at(),
            "FailureReason": "ADDITIONAL_VERIFICATION_REQUIRED",
            "Status": status,
            "SubjectAlternativeNames": ["example.com", "www.example.com"],
        }
    )

    assert isinstance(result, ModuleExit)
    assert result.values == {"changed": True, "certificate_arn": "arn:replayed"}
    # The certificate listing wait runs.
    assert query.call_count == 2 + plugin.CERTIFICATE_LIST_ATTEMPTS


@pytest.mark.parametrize("domain_name", ["example.com", "EXAMPLE.com"])
def test_supplied_token_replaying_a_certificate_listed_before_the_request_fails_without_changes(domain_name):
    # A certificate that FAILED right after an earlier request is replayed within the clock-skew window.
    result, _query = run_token_request(
        {
            "CreatedAt": created_now(),
            "FailureReason": "ADDITIONAL_VERIFICATION_REQUIRED",
            "Status": "FAILED",
            "SubjectAlternativeNames": ["example.com", "www.example.com"],
        },
        listed=[
            {"CertificateArn": "arn:other", "DomainName": "other.example.com"},
            {"CertificateArn": "arn:replayed", "DomainName": domain_name},
        ],
    )

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "msg": (
            "idempotency_token Token_1 was already used to request AWS Certificate Manager certificate arn:replayed, "
            "which is FAILED; use a new idempotency_token or omit it"
        ),
        "certificate_arn": "arn:replayed",
    }


def test_list_certificate_arns_matches_the_domain_name_in_any_status():
    summaries = [
        {"CertificateArn": "arn:failed", "DomainName": "Example.com", "Status": "FAILED"},
        {"CertificateArn": "arn:other", "DomainName": "other.example.com"},
        {"CertificateArn": "arn:no-domain"},
        "invalid",
    ]
    with patch.object(plugin, "query_list", return_value=summaries) as query:
        assert plugin.list_certificate_arns(FakeModule({}), Mock(), "example.com") == {"arn:failed"}

    assert query.call_args.kwargs == {
        "CertificateStatuses": plugin.CERTIFICATE_STATUSES,
        "Includes": {"keyTypes": plugin.CERTIFICATE_KEY_TYPES},
    }


@pytest.mark.parametrize("created_at", [None, "2026-11-13T00:00:00Z"])
def test_supplied_token_certificate_without_a_creation_time_fails_as_changed(created_at):
    result, _query = run_token_request(
        {"CreatedAt": created_at, "Status": "FAILED", "SubjectAlternativeNames": ["example.com", "www.example.com"]}
    )

    assert isinstance(result, ModuleFail)
    assert result.values == {
        "changed": True,
        "msg": "AWS Certificate Manager did not return a creation time for certificate arn:replayed",
        "certificate_arn": "arn:replayed",
    }


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


# With the key-type filter, ACM lists an imported certificate that has no common name or DNS name without DomainName.
DOMAINLESS_SUMMARY = {
    "CertificateArn": "arn:no-domain",
    "HasAdditionalSubjectAlternativeNames": False,
    "KeyAlgorithm": "RSA-2048",
    "Status": "ISSUED",
    "SubjectAlternativeNameSummaries": [],
    "Type": "IMPORTED",
}


def test_summaries_without_a_domain_name_are_skipped():
    client = Mock()
    client.describe_certificate.return_value = issued_certificate("arn:match")
    summaries = [
        DOMAINLESS_SUMMARY,
        {"CertificateArn": "arn:empty-domain", "DomainName": ""},
        {"CertificateArn": "arn:match", "DomainName": "example.com"},
    ]

    result = run_request(client, summaries)

    assert result == {"changed": False, "certificate_arn": "arn:match"}
    client.describe_certificate.assert_called_once_with(CertificateArn="arn:match", aws_retry=True)
    client.request_certificate.assert_not_called()


def test_check_mode_predicts_request_next_to_summaries_without_a_domain_name():
    client = Mock()
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": None,
            "tags": None,
        },
        check_mode=True,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[DOMAINLESS_SUMMARY]),
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    assert result.value.values == {"changed": True}
    client.describe_certificate.assert_not_called()
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


def run_tagged_request(client, tags, check_mode=False, purge_tags=True):
    client.describe_certificate.return_value = issued_certificate("arn:match")
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": purge_tags,
            "subject_alternative_names": None,
            "tags": tags,
        },
        check_mode=check_mode,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[{"CertificateArn": "arn:match", "DomainName": "example.com"}]),
        pytest.raises((ModuleExit, ModuleFail)) as result,
    ):
        plugin.main()

    return result.value.values


def test_key_only_tags_match_empty_desired_values():
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": [{"Key": "Flag"}, {"Key": "Name", "Value": "web"}]}

    result = run_tagged_request(client, {"Flag": "", "Name": "web"})

    assert result["changed"] is False
    client.add_tags_to_certificate.assert_not_called()
    client.remove_tags_from_certificate.assert_not_called()


def test_key_only_tags_are_updated_and_purged():
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": [{"Key": "Flag"}, {"Key": "Old"}]}

    result = run_tagged_request(client, {"Flag": "on"})

    assert result["changed"] is True
    client.remove_tags_from_certificate.assert_called_once_with(
        CertificateArn="arn:match", Tags=[{"Key": "Old"}], aws_retry=True
    )
    client.add_tags_to_certificate.assert_called_once_with(
        CertificateArn="arn:match", Tags=[{"Key": "Flag", "Value": "on"}], aws_retry=True
    )


@pytest.mark.parametrize(
    "response",
    [None, {"Tags": None}, {"Tags": ["Name"]}, {"Tags": [{"Value": "web"}]}, {"Tags": [{"Key": "Name", "Value": 1}]}],
)
def test_rejects_invalid_certificate_tags(response):
    client = Mock()
    client.list_tags_for_certificate.return_value = response

    result = run_tagged_request(client, {"Name": "web"})

    assert result["msg"] == "AWS Certificate Manager returned invalid tags for certificate arn:match"
    client.add_tags_to_certificate.assert_not_called()


@pytest.mark.parametrize(("current_tags", "changed"), [([{"Key": "Old", "Value": "x"}], True), ([], False)])
def test_tag_failure_reports_whether_tags_were_removed(current_tags, changed):
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": current_tags}
    client.add_tags_to_certificate.side_effect = plugin.ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "failed"}}, "AddTagsToCertificate"
    )

    result = run_tagged_request(client, {"Name": "web"})

    assert result["msg"] == "Unable to tag AWS Certificate Manager certificate arn:match"
    assert result["changed"] is changed
    assert client.remove_tags_from_certificate.called is changed


@pytest.mark.parametrize("check_mode", [True, False])
def test_rejects_merged_tags_over_the_limit_before_any_write(check_mode):
    client = Mock()
    client.list_tags_for_certificate.return_value = {
        "Tags": [{"Key": f"Existing{index}", "Value": "x"} for index in range(50)]
    }

    result = run_tagged_request(client, {"New": "y"}, check_mode=check_mode, purge_tags=False)

    assert result["msg"] == "The resulting certificate tags must contain at most 50 entries"
    client.add_tags_to_certificate.assert_not_called()
    client.remove_tags_from_certificate.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize(
    "tags", [{"Team": "R&D"}, {"Team": "a,b"}, {"Team#1": "x"}], ids=["ampersand", "comma", "hash-key"]
)
def test_tag_characters_aws_rejects_fail_before_aws(check_mode, tags):
    # ACM rejects these with ValidationException on request and when tagging, which an existing certificate reaches
    # only after its purged tags are removed.
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": None,
            "tags": tags,
        },
        check_mode=check_mode,
    )
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


def test_tags_with_characters_aws_accepts_are_added():
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": []}

    result = run_tagged_request(client, {"Team": "a b_.:/=+-@é1", "日本": ""})

    assert result["changed"] is True
    client.add_tags_to_certificate.assert_called_once()
    request = client.add_tags_to_certificate.call_args.kwargs
    assert request["CertificateArn"] == "arn:match"
    assert sorted(request["Tags"], key=lambda tag: tag["Key"]) == [
        {"Key": "Team", "Value": "a b_.:/=+-@é1"},
        {"Key": "日本", "Value": ""},
    ]


def test_tag_limit_ignores_aws_reserved_tags():
    client = Mock()
    client.list_tags_for_certificate.return_value = {
        "Tags": [{"Key": f"Existing{index}", "Value": "x"} for index in range(49)]
        + [{"Key": "AWS:Reserved", "Value": "x"}]
    }

    result = run_tagged_request(client, {"New": "y"}, purge_tags=False)

    assert result["changed"] is True
    client.add_tags_to_certificate.assert_called_once_with(
        CertificateArn="arn:match", Tags=[{"Key": "New", "Value": "y"}], aws_retry=True
    )


def test_merged_tags_under_the_limit_are_added():
    client = Mock()
    client.list_tags_for_certificate.return_value = {
        "Tags": [{"Key": f"Existing{index}", "Value": "x"} for index in range(49)]
    }

    result = run_tagged_request(client, {"New": "y"}, purge_tags=False)

    assert result["changed"] is True
    client.remove_tags_from_certificate.assert_not_called()
    client.add_tags_to_certificate.assert_called_once_with(
        CertificateArn="arn:match", Tags=[{"Key": "New", "Value": "y"}], aws_retry=True
    )


def test_request_without_an_arn_reports_changed():
    client = Mock(request_certificate=Mock(return_value={}))
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
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleFail) as raised,
    ):
        plugin.main()

    assert raised.value.values["changed"] is True


def test_wait_for_certificate_listing_returns_once_listed(no_sleep):
    module = FakeModule({})
    with patch.object(
        plugin,
        "query_list",
        side_effect=[[{"CertificateArn": "arn:other"}], [{"CertificateArn": "arn:new"}]],
    ) as query:
        plugin.wait_for_certificate_listing(module, Mock(), "arn:new")

    assert query.call_count == 2
    assert query.call_args.kwargs == {"changed": True}
    no_sleep.assert_called_once_with(plugin.CERTIFICATE_LIST_DELAY)
    assert module.warnings == []


def test_wait_for_certificate_listing_is_bounded(no_sleep):
    module = FakeModule({})
    with patch.object(plugin, "query_list", return_value=[]) as query:
        plugin.wait_for_certificate_listing(module, Mock(), "arn:new")

    assert query.call_count == plugin.CERTIFICATE_LIST_ATTEMPTS
    assert no_sleep.call_count == plugin.CERTIFICATE_LIST_ATTEMPTS - 1
    assert "arn:new" in module.warnings[0]


def test_rerun_after_request_reuses_listed_certificate():
    listed = {"CertificateArn": "arn:new", "DomainName": "example.com"}
    client = Mock()
    client.request_certificate.return_value = {"CertificateArn": "arn:new"}
    client.describe_certificate.return_value = issued_certificate("arn:new", Status="PENDING_VALIDATION")
    params = {
        "domain_name": "example.com",
        "idempotency_token": None,
        "purge_tags": True,
        "subject_alternative_names": None,
        "tags": None,
    }
    results = []
    # The first run requests the certificate and waits until it is listed; the rerun finds it.
    with (
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", side_effect=[[], [], [listed], [listed]]),
    ):
        for run in ("create", "rerun"):
            with (
                patch.object(plugin, "AnsibleAWSModule", return_value=FakeModule(params, client=client)),
                pytest.raises(ModuleExit) as result,
            ):
                plugin.main()

            results.append((run, result.value.values))

    assert results == [
        ("create", {"changed": True, "certificate_arn": "arn:new"}),
        ("rerun", {"changed": False, "certificate_arn": "arn:new"}),
    ]
    client.request_certificate.assert_called_once()


def test_check_mode_predicts_request_without_waiting():
    client = Mock()
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": None,
            "purge_tags": True,
            "subject_alternative_names": None,
            "tags": None,
        },
        check_mode=True,
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]) as query,
        pytest.raises(ModuleExit) as result,
    ):
        plugin.main()

    assert result.value.values == {"changed": True}
    query.assert_called_once()
    client.request_certificate.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
@pytest.mark.parametrize("key", ["aws:team", "AWS:team", "Aws:team"])
def test_reserved_tag_key_fails_before_any_tag_write(key, check_mode):
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": [{"Key": "Old", "Value": "x"}]}

    result = run_tagged_request(client, {key: "a"}, check_mode=check_mode)

    assert result["msg"] == "tag keys beginning with aws: are reserved and cannot be set"
    assert result.get("changed", False) is False
    client.add_tags_to_certificate.assert_not_called()
    client.remove_tags_from_certificate.assert_not_called()


@pytest.mark.parametrize("check_mode", [False, True])
def test_unchanged_reserved_tag_key_and_aws_value_are_accepted(check_mode):
    client = Mock()
    client.list_tags_for_certificate.return_value = {"Tags": [{"Key": "aws:team", "Value": "a"}]}

    result = run_tagged_request(client, {"aws:team": "a", "Team": "aws:platform"}, check_mode=check_mode)

    assert result["changed"] is True
    if check_mode:
        client.add_tags_to_certificate.assert_not_called()
    else:
        client.add_tags_to_certificate.assert_called_once()


def test_supplied_token_certificate_not_yet_described_is_retried_and_not_treated_as_a_replay(no_sleep):
    # A new certificate can take a few seconds to be described.
    not_found = plugin.ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DescribeCertificate")
    pending = {
        "Certificate": {
            "CreatedAt": created_now(),
            "Status": "PENDING_VALIDATION",
            "SubjectAlternativeNames": ["example.com", "www.example.com"],
        }
    }
    result, _query = run_token_request(not_found)
    assert isinstance(result, ModuleExit)
    assert result.values == {"changed": True, "certificate_arn": "arn:replayed"}

    client = Mock()
    client.request_certificate.return_value = {"CertificateArn": "arn:new"}
    client.describe_certificate.side_effect = [not_found, not_found, pending]
    module = FakeModule(
        {
            "domain_name": "example.com",
            "idempotency_token": "Token_1",
            "purge_tags": True,
            "subject_alternative_names": ["www.example.com"],
            "tags": None,
        },
        client=client,
    )
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods"),
        patch.object(plugin, "query_list", return_value=[]),
        pytest.raises(ModuleExit) as raised,
    ):
        plugin.main()

    assert raised.value.values == {"changed": True, "certificate_arn": "arn:new"}
    assert client.describe_certificate.call_count == 3
