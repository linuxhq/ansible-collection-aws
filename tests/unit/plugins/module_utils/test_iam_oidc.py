# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.iam_oidc import (
    get_provider_by_arn,
    normalize_provider_url,
)


def test_normalizes_provider_url():
    for value, expected in (
        (None, None),
        ("https://example.com/id/", "example.com/id"),
        ("HTTPS://example.com/id/", "example.com/id"),
        ("https://Example.COM/CaseSensitivePath/", "example.com/CaseSensitivePath"),
        ("example.com/id///", "example.com/id"),
        ("https://", ""),
    ):
        assert normalize_provider_url(value) == expected


def test_provider_includes_arn_without_response_metadata():
    client = Mock(
        get_open_id_connect_provider=Mock(
            return_value={"ClientIDList": [], "ThumbprintList": [], "Url": "example.com/id", "ResponseMetadata": {}}
        )
    )
    assert get_provider_by_arn(client, Mock(), "arn:provider") == {
        "OpenIDConnectProviderArn": "arn:provider",
        "ClientIDList": [],
        "ThumbprintList": [],
        "Url": "example.com/id",
    }
    client.get_open_id_connect_provider.assert_called_once_with(OpenIDConnectProviderArn="arn:provider", aws_retry=True)


def test_provider_rejects_invalid_response():
    client = Mock(get_open_id_connect_provider=Mock(return_value={}))
    module = Mock()
    module.fail_json.side_effect = SystemExit
    with pytest.raises(SystemExit):
        get_provider_by_arn(client, module, "arn:provider")

    module.fail_json.assert_called_once_with(
        changed=False, msg="Unable to get AWS IAM OIDC provider arn:provider: AWS returned an invalid response"
    )


def test_provider_treats_missing_lists_as_empty():
    client = Mock(get_open_id_connect_provider=Mock(return_value={"Url": "example.com/id"}))
    assert get_provider_by_arn(client, Mock(), "arn:provider") == {
        "OpenIDConnectProviderArn": "arn:provider",
        "ClientIDList": [],
        "ThumbprintList": [],
        "Url": "example.com/id",
    }


@pytest.mark.parametrize(
    "fields",
    [
        {"ClientIDList": None},
        {"ThumbprintList": "abc"},
        {"ClientIDList": [1]},
        {"ThumbprintList": [None]},
        {"Tags": None},
        {"Tags": [{"Key": "Name"}]},
    ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_provider_rejects_present_invalid_fields(fields, changed):
    client = Mock(get_open_id_connect_provider=Mock(return_value=dict({"Url": "example.com/id"}, **fields)))
    module = Mock()
    module.fail_json.side_effect = SystemExit
    with pytest.raises(SystemExit):
        get_provider_by_arn(client, module, "arn:provider", changed=changed)

    module.fail_json.assert_called_once_with(
        changed=changed, msg="Unable to get AWS IAM OIDC provider arn:provider: AWS returned an invalid response"
    )
