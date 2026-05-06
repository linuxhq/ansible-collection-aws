#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.common.collections import is_sequence
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    ansible_dict_to_boto3_filter_list,
)
from ansible_collections.linuxhq.aws.plugins.module_utils.aws import (
    aws_paginated_find,
    aws_paginated_list,
    aws_resource,
)


def _list_route53_resolver_resources(
    client,
    module,
    operation,
    result_key,
    **filters,
):
    kwargs = route53_resolver_filter_request(**filters)
    if kwargs is None:
        return []
    return aws_paginated_list(
        client,
        module,
        operation,
        result_key,
        **kwargs,
    )


def get_resolver_endpoint(client, module, resolver_endpoint_id):
    return aws_resource(
        client,
        module,
        "get_resolver_endpoint",
        "ResolverEndpoint",
        ignore_error_codes="ResourceNotFoundException",
        ignored_error_result=None,
        ResolverEndpointId=resolver_endpoint_id,
    )


def get_resolver_endpoint_by_name(client, module, name):
    return aws_paginated_find(
        client,
        module,
        "list_resolver_endpoints",
        "ResolverEndpoints",
        lambda endpoint: endpoint.get("Name") == name,
        **route53_resolver_filter_request(Name=name),
    )


def get_resolver_rule_association_by_rule_and_vpc(
    client, module, resolver_rule_id, vpc_id
):
    return aws_paginated_find(
        client,
        module,
        "list_resolver_rule_associations",
        "ResolverRuleAssociations",
        lambda association: (
            association.get("ResolverRuleId") == resolver_rule_id
            and association.get("VPCId") == vpc_id
        ),
        **route53_resolver_filter_request(
            ResolverRuleId=resolver_rule_id,
            VPCId=vpc_id,
        ),
    )


def get_resolver_rule_by_name(client, module, name):
    return aws_paginated_find(
        client,
        module,
        "list_resolver_rules",
        "ResolverRules",
        lambda rule: rule.get("Name") == name,
        **route53_resolver_filter_request(Name=name),
    )


def list_resolver_endpoints(client, module):
    return _list_route53_resolver_resources(
        client,
        module,
        "list_resolver_endpoints",
        "ResolverEndpoints",
    )


def list_resolver_rule_associations(
    client,
    module,
    name=None,
    resolver_rule_id=None,
    vpc_id=None,
):
    return _list_route53_resolver_resources(
        client,
        module,
        "list_resolver_rule_associations",
        "ResolverRuleAssociations",
        Name=name,
        ResolverRuleId=resolver_rule_id,
        VPCId=vpc_id,
    )


def list_resolver_rules(client, module):
    return _list_route53_resolver_resources(
        client,
        module,
        "list_resolver_rules",
        "ResolverRules",
    )


def resolver_endpoint_with_ip_addresses(client, module, endpoint):
    if endpoint is None or endpoint.get("Id") is None:
        return endpoint

    endpoint = dict(endpoint)
    endpoint["IpAddresses"] = aws_paginated_list(
        client,
        module,
        "list_resolver_endpoint_ip_addresses",
        "IpAddresses",
        ResolverEndpointId=endpoint["Id"],
    )
    return endpoint


def route53_resolver_filter_request(**filters):
    prepared_filters = {}
    for name, value in filters.items():
        if value is None:
            continue
        if is_sequence(value):
            value = list(value)
            if not value:
                return None
        prepared_filters[name] = value
    filters = ansible_dict_to_boto3_filter_list(prepared_filters)
    return {"Filters": filters} if filters else {}
