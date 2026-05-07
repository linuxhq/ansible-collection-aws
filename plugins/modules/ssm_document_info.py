#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
version_added: "1.9.0"
short_description: Gather information about AWS Systems Manager documents
description:
  - Gathers information about AWS Systems Manager documents.
  - Retrieves each document as JSON and parses the returned content when possible.
author:
  - Taylor Kimball (@tkimball83)
options:
  name:
    description:
      - The Systems Manager document name to gather.
    required: true
    type: str
extends_documentation_fragment:
  - amazon.aws.common.modules
  - amazon.aws.region.modules
  - amazon.aws.boto3
"""

EXAMPLES = r"""
- name: Gather information about a Systems Manager document
  linuxhq.aws.ssm_document_info:
    name: molecule-command-shell
"""

RETURN = r"""
document:
  description:
    - The AWS Systems Manager document.
  returned: always
  type: dict
"""

import json

from ansible_collections.amazon.aws.plugins.module_utils.botocore import (
    is_boto3_error_code,
)
from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.amazon.aws.plugins.module_utils.retries import AWSRetry
from ansible_collections.amazon.aws.plugins.module_utils.transformation import (
    boto3_resource_to_ansible_dict,
)

SSM_DOCUMENT_RESOURCE_TYPE = "Document"


def main():
    module = AnsibleAWSModule(
        argument_spec={"name": {"required": True, "type": "str"}},
        supports_check_mode=True,
    )
    client = module.client("ssm", retry_decorator=AWSRetry.jittered_backoff())
    try:
        document = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion="$LATEST",
            Name=module.params["name"],
            aws_retry=True,
        )
    except is_boto3_error_code(("InvalidDocument", "InvalidDocumentOperation")):
        document = {}
    except Exception as e:
        module.fail_json_aws(
            e,
            msg=f"Unable to get AWS Systems Manager document {module.params['name']}",
        )
    if document:
        try:
            document["Tags"] = client.list_tags_for_resource(
                ResourceType=SSM_DOCUMENT_RESOURCE_TYPE,
                ResourceId=module.params["name"],
                aws_retry=True,
            ).get("TagList", [])
        except Exception as e:
            module.fail_json_aws(
                e,
                msg=f"Unable to list tags for AWS Systems Manager document {module.params['name']}",
            )

    def content_transform(content):
        if content is None:
            return {}
        try:
            content = json.loads(content)
        except ValueError:
            return content
        if isinstance(content, dict):
            return boto3_resource_to_ansible_dict(
                content, transform_tags=False, force_tags=False
            )
        return content

    module.exit_json(
        changed=False,
        document=boto3_resource_to_ansible_dict(
            document,
            nested_transforms={"Content": content_transform},
            transform_tags=True,
            force_tags=False,
        ),
    )


if __name__ == "__main__":
    main()
