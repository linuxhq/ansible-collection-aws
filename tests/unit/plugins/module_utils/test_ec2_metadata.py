# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from unittest.mock import Mock

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.ec2_metadata import (
    get_instance_metadata_defaults,
)
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleFail,
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


def test_rejects_missing_account_level():
    client = Mock(get_instance_metadata_defaults=Mock(return_value={}))
    with pytest.raises(ModuleFail) as raised:
        get_instance_metadata_defaults(client, FakeModule({}, region="us-east-1"))

    assert "invalid instance metadata defaults" in raised.value.values["msg"]
