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

- name: Gather information about selected WAFv2 web ACLs
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
      description: Application integration configuration for the web ACL.
      returned: when available
      type: dict
    arn:
      description: ARN of the web ACL.
      returned: always
      type: str
    association_config:
      description: Request-body inspection settings for associated resources.
      returned: when available
      type: dict
      contains:
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
    challenge_config:
      description: Challenge configuration inherited by rules.
      returned: when available
      type: dict
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
    default_action:
      description: Action applied when no rule matches.
      returned: always
      type: dict
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
    name:
      description: Name of the web ACL.
      returned: always
      type: str
    on_source_d_do_s_protection_config:
      description: On-source DDoS protection configuration.
      returned: when available
      type: dict
    post_process_firewall_manager_rule_groups:
      description: Firewall Manager rule groups evaluated after the web ACL rules.
      returned: when available
      type: list
      elements: dict
    pre_process_firewall_manager_rule_groups:
      description: Firewall Manager rule groups evaluated before the web ACL rules.
      returned: when available
      type: list
      elements: dict
    retrofitted_by_firewall_manager:
      description: Whether Firewall Manager retrofitted the web ACL.
      returned: when available
      type: bool
    rules:
      description: Rules contained in the web ACL.
      returned: when available
      type: list
      elements: dict
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
"""

import json

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    pass

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict
from ansible.module_utils.common.text.converters import to_text

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_list_to_ansible_dict,
)

from ansible_collections.linuxhq.aws.plugins.module_utils.sdk import require_client_methods
from ansible_collections.linuxhq.aws.plugins.module_utils.wafv2 import (
    get_resource_tags,
    list_resource_summaries,
    require_lookup_params,
)


def association_config(config):
    # RequestBody is keyed by associated resource types, which are AWS values rather than field names.
    request_body = config.get("RequestBody")
    result = camel_dict_to_snake_dict({key: value for key, value in config.items() if key != "RequestBody"})
    if isinstance(request_body, dict):
        result["request_body"] = {
            resource_type: camel_dict_to_snake_dict(settings) for resource_type, settings in request_body.items()
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

    web_acls = []
    for summary in summaries:
        try:
            response = client.get_web_acl(
                Id=summary["Id"],
                Name=summary["Name"],
                Scope=scope,
                aws_retry=True,
            )
        except is_boto3_error_code("WAFNonexistentItemException"):
            continue
        except (BotoCoreError, ClientError) as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to get AWS WAFv2 web ACL {summary['Name']}/{summary['Id']}",
            )

        web_acl = response.get("WebACL") if isinstance(response, dict) else None
        if not isinstance(web_acl, dict):
            module.fail_json(
                msg=f"Unexpected response while getting AWS WAFv2 web ACL {summary['Name']}/{summary['Id']}"
            )

        tags = get_resource_tags(client, module, web_acl, "web ACL")
        if tags is None:
            continue

        web_acls.append(
            json.loads(
                json.dumps(
                    web_acl,
                    default=lambda value: (
                        to_text(
                            bytes(value) if isinstance(value, bytearray) else value,
                            errors="surrogate_or_strict",
                        )
                        if isinstance(value, (bytes, bytearray))
                        else (value.isoformat() if hasattr(value, "isoformat") else str(value))
                    ),
                )
            )
        )
        web_acls[-1]["Tags"] = tags

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
