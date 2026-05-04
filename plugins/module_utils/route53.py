#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    paginated_query_with_retries,
)
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
    boto3_resource_to_ansible_dict,
)


def list_delegation_sets(client, module):
    delegation_sets = []
    marker = None
    list_reusable_delegation_sets = AWSRetry.jittered_backoff()(
        client.list_reusable_delegation_sets
    )

    while True:
        kwargs = {}
        if marker:
            kwargs["Marker"] = marker

        try:
            response = list_reusable_delegation_sets(**kwargs)
        except Exception as e:
            module.fail_json_aws(
                e,
                msg="Unable to list AWS Route53 reusable delegation sets",
            )

        delegation_sets.extend(response.get("DelegationSets", []))
        if not response.get("IsTruncated"):
            break
        marker = response.get("NextMarker")

    return delegation_sets


def list_resolver_endpoints(client, module):
    try:
        response = paginated_query_with_retries(client, "list_resolver_endpoints")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS Route53 Resolver endpoints",
        )
    return response.get("ResolverEndpoints", [])


def list_resolver_rule_associations(client, module):
    try:
        response = paginated_query_with_retries(
            client,
            "list_resolver_rule_associations",
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS Route53 Resolver rule associations",
        )
    return response.get("ResolverRuleAssociations", [])


def list_resolver_rules(client, module):
    try:
        response = paginated_query_with_retries(client, "list_resolver_rules")
    except Exception as e:
        module.fail_json_aws(
            e,
            msg="Unable to list AWS Route53 Resolver rules",
        )
    return response.get("ResolverRules", [])


def normalize_delegation_set(delegation_set):
    return boto3_resource_to_ansible_dict(delegation_set, force_tags=False)


def normalize_resolver_endpoint_with_ip_addresses(client, module, endpoint):
    normalized = boto3_resource_to_ansible_dict(endpoint, force_tags=False)
    if endpoint is None or endpoint.get("Id") is None:
        return normalized

    try:
        response = paginated_query_with_retries(
            client,
            "list_resolver_endpoint_ip_addresses",
            ResolverEndpointId=endpoint["Id"],
        )
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=(
                "Unable to list AWS Route53 Resolver endpoint IP addresses "
                f"for {endpoint['Id']}"
            ),
        )
    normalized["ip_addresses"] = boto3_resource_list_to_ansible_dict(
        response.get("IpAddresses", []),
        force_tags=False,
    )
    return normalized


def normalize_resolver_rule(rule):
    return boto3_resource_to_ansible_dict(rule, force_tags=False)


def normalize_resolver_rule_association(association):
    return boto3_resource_to_ansible_dict(association, force_tags=False)
