from unittest.mock import Mock, patch

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils import wafv2 as wafv2_utils
from ansible_collections.linuxhq.aws.plugins.modules import wafv2_ip_set_info as plugin
from ansible_collections.linuxhq.aws.tests.unit.plugins.modules.utils import (
    FakeModule,
    ModuleExit,
    ModuleFail,
    assert_module_contract,
)

IP_SET = {"Addresses": [], "ARN": "arn:ip-set", "Id": "wanted", "IPAddressVersion": "IPV4", "Name": "target"}


def params(**overrides):
    values = {"id": None, "name": None, "scope": "regional"}
    values.update(overrides)
    return values


def ip_set_client(tags=None):
    return Mock(
        get_ip_set=Mock(return_value={"IPSet": IP_SET}),
        list_tags_for_resource=Mock(return_value={"TagInfoForResource": {"TagList": tags or []}}),
    )


def run(module, summaries=None):
    with (
        patch.object(plugin, "AnsibleAWSModule", return_value=module),
        patch.object(plugin, "require_client_methods") as require_client_methods,
        patch.object(wafv2_utils, "query_list", return_value=summaries) as query_list,
        pytest.raises((ModuleExit, ModuleFail)) as raised,
    ):
        plugin.main()

    return raised.value, require_client_methods, query_list


def test_module_contract():
    captured = assert_module_contract(plugin)

    assert captured["argument_spec"]["scope"]["choices"] == ["cloudfront", "regional"]


def test_cloudfront_scope_is_uppercase_for_aws():
    _result, _require, query_list = run(FakeModule(params(scope="cloudfront"), client=Mock()), [])

    assert query_list.call_args.kwargs["Scope"] == "CLOUDFRONT"


def test_tags_are_returned_with_their_case():
    client = ip_set_client([{"Key": "Name", "Value": "target"}, {"Key": "CostCenter", "Value": "A1"}])
    result, require_client_methods, _query = run(FakeModule(params(), client=client), [IP_SET])

    assert result.values["ip_sets"][0]["tags"] == {"Name": "target", "CostCenter": "A1"}
    assert "list_tags_for_resource" in require_client_methods.call_args.args[3]


def test_id_and_name_get_the_ip_set_without_listing():
    client = ip_set_client()
    result, _require, query_list = run(FakeModule(params(id="wanted", name="target"), client=client), [])

    query_list.assert_not_called()
    client.get_ip_set.assert_called_once_with(Id="wanted", Name="target", Scope="REGIONAL", aws_retry=True)
    assert result.values["ip_sets"] == [
        {
            "addresses": [],
            "arn": "arn:ip-set",
            "id": "wanted",
            "ip_address_version": "IPV4",
            "name": "target",
            "tags": {},
        }
    ]
