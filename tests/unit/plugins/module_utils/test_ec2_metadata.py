# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_metadata import (
    get_instance_metadata_defaults,
)


def test_gets_and_normalizes_account_defaults():
    client = Mock(
        get_instance_metadata_defaults=Mock(
            return_value={"AccountLevel": {"HttpEndpoint": "enabled", "HttpTokens": "required"}}
        )
    )
    assert get_instance_metadata_defaults(client, Mock(region="us-east-1")) == {
        "http_endpoint": "enabled",
        "http_tokens": "required",
    }
    client.get_instance_metadata_defaults.assert_called_once_with(aws_retry=True)
