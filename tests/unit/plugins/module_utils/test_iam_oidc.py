# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest import TestCase
from unittest.mock import Mock

from ansible_collections.linuxhq.aws.plugins.module_utils.iam_oidc import (
    get_provider_by_arn,
    normalize_provider_url,
)


class IamOidcTests(TestCase):
    def test_normalizes_provider_url(self):
        for value, expected in (
            (None, None),
            ("https://example.com/id/", "example.com/id"),
            ("HTTPS://example.com/id/", "example.com/id"),
            ("https://Example.COM/CaseSensitivePath/", "example.com/CaseSensitivePath"),
            ("example.com/id///", "example.com/id"),
            ("https://", ""),
        ):
            with self.subTest(value=value):
                self.assertEqual(normalize_provider_url(value), expected)

    def test_provider_includes_arn_without_response_metadata(self):
        client = Mock(
            get_open_id_connect_provider=Mock(
                return_value={
                    "ClientIDList": [],
                    "ThumbprintList": [],
                    "Url": "example.com/id",
                    "ResponseMetadata": {},
                }
            )
        )

        self.assertEqual(
            get_provider_by_arn(client, Mock(), "arn:provider"),
            {
                "OpenIDConnectProviderArn": "arn:provider",
                "ClientIDList": [],
                "ThumbprintList": [],
                "Url": "example.com/id",
            },
        )
        client.get_open_id_connect_provider.assert_called_once_with(
            OpenIDConnectProviderArn="arn:provider", aws_retry=True
        )

    def test_provider_rejects_invalid_response(self):
        client = Mock(get_open_id_connect_provider=Mock(return_value={}))
        module = Mock()
        module.fail_json.side_effect = SystemExit

        with self.assertRaises(SystemExit):
            get_provider_by_arn(client, module, "arn:provider")

        module.fail_json.assert_called_once_with(
            msg="Unable to get AWS IAM OIDC provider arn:provider: AWS returned an invalid response"
        )
