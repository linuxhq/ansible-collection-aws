#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: wafv2_web_acl_info
version_added: '1.9.0'
short_description: Gather information about AWS WAFv2 web ACLs
description:
  - Gathers information about AWS WAFv2 web ACLs.
  - Lists web ACLs for the requested scope and returns each full web ACL definition
    with its tags.
author:
  - Taylor Kimball (@tkimball83)
options:
  id:
    description:
      - WAFv2 web ACL ID used to limit the result set.
      - This must not be empty when specified.
      - The module lists web ACL summaries for the selected O(scope), filters
        by ID, and then gathers each full web ACL definition.
      - When both O(id) and O(name) are specified, the module gets the web ACL
        directly without listing summaries.
      - A web ACL ID that does not exist results in an empty list.
    type: str
  name:
    description:
      - WAFv2 web ACL name used to limit the result set.
      - This must not be empty when specified.
      - The module lists web ACL summaries for the selected O(scope), filters
        by name, and then gathers each full web ACL definition.
      - When both O(id) and O(name) are specified, the module gets the web ACL
        directly without listing summaries.
      - A web ACL that does not exist results in an empty list.
    type: str
  scope:
    description:
      - The scope of the web ACLs to gather.
      - Use C(cloudfront) for global web ACLs and C(regional) for regional web ACLs.
      - V(cloudfront) requires the C(us-east-1) region; any other region fails
        before AWS is called.
    choices:
      - cloudfront
      - regional
    default: regional
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
attributes:
  check_mode:
    description: This module only gathers information and does not modify resources.
    support: full
  diff_mode:
    description: This module does not return diff output.
    support: none
"""

EXAMPLES = r"""
- name: Gather information about regional WAFv2 web ACLs
  linuxhq.aws.wafv2_web_acl_info:

- name: Gather information about CloudFront WAFv2 web ACLs
  linuxhq.aws.wafv2_web_acl_info:
    scope: cloudfront
    region: us-east-1

- name: Gather information about a selected WAFv2 web ACL
  linuxhq.aws.wafv2_web_acl_info:
    name: molecule
"""

RETURN = r"""
scope:
  description: The AWS WAFv2 scope that was queried.
  returned: always
  type: str
web_acls:
  description:
    - A list of AWS WAFv2 web ACL definitions.
  returned: always
  type: list
  elements: dict
  contains:
    application_config:
      description: Application attributes recorded when the web ACL was created, which WAF uses to recommend protection packs.
      returned: when available
      type: dict
      contains:
        attributes:
          description:
            - The application attributes.
            - Each attribute also contains C(values), the list of attribute value
              strings; read it as C(attribute["values"]) because Jinja dot
              notation cannot access a key named C(values).
          returned: when available
          type: list
          elements: dict
          contains:
            name:
              description: The attribute name.
              returned: when available
              type: str
    arn:
      description: ARN of the web ACL.
      returned: always
      type: str
    association_config:
      description:
        - Custom settings for the associations between the web ACL and
          protected resources.
      returned: when available
      type: dict
      contains:
        challenge_javascript_sdk_injection:
          description:
            - Resource types whose responses get the WAF challenge JavaScript
              SDK inserted, keyed as AWS returns them, such as C(CLOUDFRONT).
            - Each value is empty.
          returned: when available
          type: dict
        request_body:
          description:
            - Request-body inspection settings keyed by associated resource type.
            - Resource types, such as C(CLOUDFRONT) and C(API_GATEWAY), are
              returned as AWS returns them; their settings use snake_case.
          returned: when available
          type: dict
    capacity:
      description: Web ACL capacity units currently used.
      returned: when available
      type: int
    captcha_config:
      description: CAPTCHA configuration inherited by rules.
      returned: when available
      type: dict
      contains:
        immunity_time_property:
          description: How long a CAPTCHA timestamp in the token remains valid after the client solves a CAPTCHA puzzle.
          returned: when available
          type: dict
          contains:
            immunity_time:
              description: The number of seconds that WAF considers the timestamp valid.
              returned: when available
              type: int
    challenge_config:
      description: Challenge configuration inherited by rules.
      returned: when available
      type: dict
      contains:
        immunity_time_property:
          description: How long a challenge timestamp in the token remains valid after the client responds to a challenge.
          returned: when available
          type: dict
          contains:
            immunity_time:
              description: The number of seconds that WAF considers the timestamp valid.
              returned: when available
              type: int
    custom_response_bodies:
      description:
        - Custom response bodies available to web ACL rules.
        - Body names retain their original case; body fields use snake_case.
      returned: when available
      type: dict
    data_protection_config:
      description: Data protection configuration for the web ACL.
      returned: when available
      type: dict
      contains:
        data_protections:
          description: Data protection configurations for specific web request field types.
          returned: when available
          type: list
          elements: dict
          contains:
            action:
              description: How the field is protected.
              returned: when available
              type: str
            exclude_rate_based_details:
              description: Whether rate-based rule details are also excluded from the data protection for the field.
              returned: when available
              type: bool
            exclude_rule_match_details:
              description: Whether rule match details are also excluded from the data protection for the field.
              returned: when available
              type: bool
            field:
              description: The field type and optional keys that the protection applies to.
              returned: when available
              type: dict
              contains:
                field_keys:
                  description: The keys to protect for the field type.
                  returned: when available
                  type: list
                  elements: str
                field_type:
                  description: The web request component type to protect.
                  returned: when available
                  type: str
    default_action:
      description: Action applied when no rule matches.
      returned: always
      type: dict
      contains:
        allow:
          description: Present when WAF allows requests by default.
          returned: when available
          type: dict
          contains:
            custom_request_handling:
              description: Custom handling for the web request.
              returned: when available
              type: dict
              contains:
                insert_headers:
                  description: The HTTP headers to insert into the request.
                  returned: when available
                  type: list
                  elements: dict
                  contains:
                    name:
                      description: The name of the custom header.
                      returned: when available
                      type: str
                    value:
                      description: The value of the custom header.
                      returned: when available
                      type: str
        block:
          description: Present when WAF blocks requests by default.
          returned: when available
          type: dict
          contains:
            custom_response:
              description: A custom response for the web request.
              returned: when available
              type: dict
              contains:
                custom_response_body_key:
                  description: The key of the custom response body that WAF returns to the client.
                  returned: when available
                  type: str
                response_code:
                  description: The HTTP status code to return to the client.
                  returned: when available
                  type: int
                response_headers:
                  description: The HTTP headers to use in the response.
                  returned: when available
                  type: list
                  elements: dict
                  contains:
                    name:
                      description: The name of the custom header.
                      returned: when available
                      type: str
                    value:
                      description: The value of the custom header.
                      returned: when available
                      type: str
    description:
      description: Description of the web ACL.
      returned: when available
      type: str
    id:
      description: ID of the web ACL.
      returned: always
      type: str
    label_namespace:
      description: Namespace used for labels added by the web ACL.
      returned: when available
      type: str
    managed_by_firewall_manager:
      description: Whether Firewall Manager manages the web ACL.
      returned: when available
      type: bool
    monetization_config:
      description: Monetization configuration for the web ACL.
      returned: when available
      type: dict
      contains:
        crypto_config:
          description: The cryptocurrency payment configuration, including the blockchain networks and wallet addresses that receive payments.
          returned: when available
          type: dict
          contains:
            payment_networks:
              description: The blockchain payment networks configured to receive payments.
              returned: when available
              type: list
              elements: dict
              contains:
                chain:
                  description: The blockchain network for receiving payments.
                  returned: when available
                  type: str
                prices:
                  description: The price configuration for this payment network.
                  returned: when available
                  type: list
                  elements: dict
                  contains:
                    amount:
                      description: The price per request as a decimal string in the specified currency.
                      returned: when available
                      type: str
                    currency:
                      description: The cryptocurrency for payment.
                      returned: when available
                      type: str
                wallet_address:
                  description: The wallet address on the blockchain network where payments are sent.
                  returned: when available
                  type: str
        currency_mode:
          description: Whether the configuration uses real or test currency, C(REAL) or C(TEST).
          returned: when available
          type: str
    name:
      description: Name of the web ACL.
      returned: always
      type: str
    on_source_d_do_s_protection_config:
      description: On-source DDoS protection configuration.
      returned: when available
      type: dict
      contains:
        alb_low_reputation_mode:
          description: The level of DDoS protection that applies to web ACLs associated with Application Load Balancers.
          returned: when available
          type: str
    post_process_firewall_manager_rule_groups:
      description: Firewall Manager rule groups evaluated after the web ACL rules.
      returned: when available
      type: list
      elements: dict
      contains:
        firewall_manager_statement:
          description:
            - The Firewall Manager rule group reference statement.
            - Bytes of a byte match C(search_string) that are not valid UTF-8 are replaced with U+FFFD.
          returned: when available
          type: dict
        name:
          description: The name of the rule group.
          returned: when available
          type: str
        override_action:
          description: The action used in place of the action that results from the rule group evaluation.
          returned: when available
          type: dict
          contains:
            count:
              description: Present when the rule group evaluation result is overridden to count only.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            none:
              description: Present when the rule group evaluation result is not overridden.
              returned: when available
              type: dict
        priority:
          description: The order in which WAF evaluates the rule group, starting from the lowest priority.
          returned: when available
          type: int
        visibility_config:
          description: The CloudWatch metrics and web request sampling configuration.
          returned: when available
          type: dict
          contains:
            cloud_watch_metrics_enabled:
              description: Whether the associated resource sends metrics to CloudWatch.
              returned: when available
              type: bool
            metric_name:
              description: The name of the CloudWatch metric dimension.
              returned: when available
              type: str
            sampled_requests_enabled:
              description: Whether WAF stores a sampling of the web requests that match the rules.
              returned: when available
              type: bool
    pre_process_firewall_manager_rule_groups:
      description: Firewall Manager rule groups evaluated before the web ACL rules.
      returned: when available
      type: list
      elements: dict
      contains:
        firewall_manager_statement:
          description:
            - The Firewall Manager rule group reference statement.
            - Bytes of a byte match C(search_string) that are not valid UTF-8 are replaced with U+FFFD.
          returned: when available
          type: dict
        name:
          description: The name of the rule group.
          returned: when available
          type: str
        override_action:
          description: The action used in place of the action that results from the rule group evaluation.
          returned: when available
          type: dict
          contains:
            count:
              description: Present when the rule group evaluation result is overridden to count only.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            none:
              description: Present when the rule group evaluation result is not overridden.
              returned: when available
              type: dict
        priority:
          description: The order in which WAF evaluates the rule group, starting from the lowest priority.
          returned: when available
          type: int
        visibility_config:
          description: The CloudWatch metrics and web request sampling configuration.
          returned: when available
          type: dict
          contains:
            cloud_watch_metrics_enabled:
              description: Whether the associated resource sends metrics to CloudWatch.
              returned: when available
              type: bool
            metric_name:
              description: The name of the CloudWatch metric dimension.
              returned: when available
              type: str
            sampled_requests_enabled:
              description: Whether WAF stores a sampling of the web requests that match the rules.
              returned: when available
              type: bool
    retrofitted_by_firewall_manager:
      description: Whether Firewall Manager retrofitted the web ACL.
      returned: when available
      type: bool
    rules:
      description: Rules contained in the web ACL.
      returned: when available
      type: list
      elements: dict
      contains:
        action:
          description: The action that WAF takes on a web request that matches the rule statement.
          returned: when available
          type: dict
          contains:
            allow:
              description: Present when WAF allows the web request.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            block:
              description: Present when WAF blocks the web request.
              returned: when available
              type: dict
              contains:
                custom_response:
                  description: A custom response for the web request.
                  returned: when available
                  type: dict
                  contains:
                    custom_response_body_key:
                      description: The key of the custom response body that WAF returns to the client.
                      returned: when available
                      type: str
                    response_code:
                      description: The HTTP status code to return to the client.
                      returned: when available
                      type: int
                    response_headers:
                      description: The HTTP headers to use in the response.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            captcha:
              description: Present when WAF runs a CAPTCHA check against the web request.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request when its token is valid and unexpired.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            challenge:
              description: Present when WAF runs a challenge check against the web request.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request when its token is valid and unexpired.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            count:
              description: Present when WAF counts the web request and continues evaluating the remaining rules.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            monetize:
              description: Present when WAF returns an HTTP 402 Payment Required response with a price manifest.
              returned: when available
              type: dict
              contains:
                price_multiplier:
                  description: The multiplier applied to the base price defined in the web ACL monetization configuration.
                  returned: when available
                  type: str
        captcha_config:
          description: How WAF handles CAPTCHA evaluations for the rule.
          returned: when available
          type: dict
          contains:
            immunity_time_property:
              description: How long a CAPTCHA timestamp in the token remains valid after the client solves a CAPTCHA puzzle.
              returned: when available
              type: dict
              contains:
                immunity_time:
                  description: The number of seconds that WAF considers the timestamp valid.
                  returned: when available
                  type: int
        challenge_config:
          description: How WAF handles challenge evaluations for the rule.
          returned: when available
          type: dict
          contains:
            immunity_time_property:
              description: How long a challenge timestamp in the token remains valid after the client responds to a challenge.
              returned: when available
              type: dict
              contains:
                immunity_time:
                  description: The number of seconds that WAF considers the timestamp valid.
                  returned: when available
                  type: int
        name:
          description: The name of the rule.
          returned: when available
          type: str
        override_action:
          description: The action used in place of the action that results from the rule group evaluation.
          returned: when available
          type: dict
          contains:
            count:
              description: Present when the rule group evaluation result is overridden to count only.
              returned: when available
              type: dict
              contains:
                custom_request_handling:
                  description: Custom handling for the web request.
                  returned: when available
                  type: dict
                  contains:
                    insert_headers:
                      description: The HTTP headers to insert into the request.
                      returned: when available
                      type: list
                      elements: dict
                      contains:
                        name:
                          description: The name of the custom header.
                          returned: when available
                          type: str
                        value:
                          description: The value of the custom header.
                          returned: when available
                          type: str
            none:
              description: Present when the rule group evaluation result is not overridden.
              returned: when available
              type: dict
        priority:
          description: The order in which WAF evaluates the rule, starting from the lowest priority.
          returned: when available
          type: int
        rule_labels:
          description: Labels applied to web requests that match the rule statement.
          returned: when available
          type: list
          elements: dict
          contains:
            name:
              description: The label string.
              returned: when available
              type: str
        statement:
          description:
            - The WAF processing statement for the rule, such as a byte match or size constraint statement.
            - Bytes of a byte match C(search_string) that are not valid UTF-8 are replaced with U+FFFD.
          returned: when available
          type: dict
        visibility_config:
          description: The CloudWatch metrics and web request sampling configuration.
          returned: when available
          type: dict
          contains:
            cloud_watch_metrics_enabled:
              description: Whether the associated resource sends metrics to CloudWatch.
              returned: when available
              type: bool
            metric_name:
              description: The name of the CloudWatch metric dimension.
              returned: when available
              type: str
            sampled_requests_enabled:
              description: Whether WAF stores a sampling of the web requests that match the rules.
              returned: when available
              type: bool
    tags:
      description:
        - Tags of the web ACL.
        - Tag keys keep their original case.
      returned: always
      type: dict
    token_domains:
      description: Domains accepted in WAF tokens.
      returned: when available
      type: list
      elements: str
    visibility_config:
      description: Sampling, metrics, and CloudWatch configuration.
      returned: always
      type: dict
      contains:
        cloud_watch_metrics_enabled:
          description: Whether the associated resource sends metrics to CloudWatch.
          returned: when available
          type: bool
        metric_name:
          description: The name of the CloudWatch metric dimension.
          returned: when available
          type: str
        sampled_requests_enabled:
          description: Whether WAF stores a sampling of the web requests that match the rules.
          returned: when available
          type: bool
"""

import json

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict
from ansible.module_utils.common.text.converters import to_text

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods
from ansible_collections.linuxhq.aws.plugins.module_utils.wafv2 import (
    get_resources_with_tags,
    list_resource_summaries,
    require_lookup_params,
)

# AssociationConfig members keyed by associated resource types, which are AWS values rather than field names.
RESOURCE_TYPE_MAPS = {
    "ChallengeJavascriptSdkInjection": "challenge_javascript_sdk_injection",
    "RequestBody": "request_body",
}


def json_default(value):
    # SearchString is the only WebACL member JSON cannot encode; botocore returns blobs as bytes. WAF stores any
    # bytes, and the controller rejects the lone surrogates that surrogate_* handlers decode invalid UTF-8 to, so
    # invalid UTF-8 becomes U+FFFD.
    return to_text(value, errors="replace")


def association_config(config):
    result = camel_dict_to_snake_dict({key: value for key, value in config.items() if key not in RESOURCE_TYPE_MAPS})
    for key, name in RESOURCE_TYPE_MAPS.items():
        resource_types = config.get(key)
        if isinstance(resource_types, dict):
            result[name] = {
                resource_type: camel_dict_to_snake_dict(settings) for resource_type, settings in resource_types.items()
            }

    return result


def main():
    argument_spec = {
        "id": {"type": "str"},
        "name": {"type": "str"},
        "scope": {
            "choices": ["cloudfront", "regional"],
            "default": "regional",
            "type": "str",
        },
    }

    module = AnsibleAWSModule(argument_spec=argument_spec, supports_check_mode=True)
    require_lookup_params(module)

    client = module.client("wafv2", retry_decorator=AWSRetry.jittered_backoff())
    require_client_methods(
        module,
        client,
        "WAFv2",
        {
            "list_web_acls": ("Limit", "NextMarker", "Scope"),
            "get_web_acl": ("Id", "Name", "Scope"),
            "list_tags_for_resource": ("NextMarker", "ResourceARN"),
        },
    )

    scope = module.params["scope"].upper()
    summaries = list_resource_summaries(client, module, "list_web_acls", "WebACLs", "web ACLs", scope)

    web_acls = [
        dict(json.loads(json.dumps(web_acl, default=json_default)), Tags=tags)
        for web_acl, tags in get_resources_with_tags(
            client, module, summaries, "get_web_acl", "WebACL", "web ACL", scope
        )
    ]

    module.exit_json(
        changed=False,
        scope=scope.lower(),
        web_acls=boto3_resource_list_to_ansible_dict(
            web_acls,
            transform_tags=False,
            force_tags=False,
            ignore_list=["Tags"],
            nested_transforms={
                "AssociationConfig": association_config,
                "CustomResponseBodies": lambda bodies: {
                    name: camel_dict_to_snake_dict(body) for name, body in bodies.items()
                },
            },
        ),
    )


if __name__ == "__main__":
    main()
