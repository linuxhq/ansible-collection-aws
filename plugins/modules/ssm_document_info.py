#!/usr/bin/python
# Copyright: Taylor Kimball
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
---
module: ssm_document_info
version_added: 1.9.1
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

from ansible.module_utils.common.dict_transformations import camel_dict_to_snake_dict

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule


def is_not_found_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in (
        "InvalidDocument",
        "InvalidDocumentOperation",
    )


def get_document(client, module, name):
    try:
        response = client.get_document(
            DocumentFormat="JSON",
            DocumentVersion="$LATEST",
            Name=name,
        )
    except Exception as e:
        if is_not_found_error(e):
            return {}
        module.fail_json_aws(
            e, msg=f"Unable to get AWS Systems Manager document {name}"
        )

    document = camel_dict_to_snake_dict(response)
    content = response.get("Content")
    if content is not None:
        try:
            document["content"] = json.loads(content)
        except ValueError:
            document["content"] = content
    return document


def main():
    module = AnsibleAWSModule(
        argument_spec={"name": {"required": True, "type": "str"}},
        supports_check_mode=True,
    )
    client = module.client("ssm")

    module.exit_json(
        changed=False,
        document=get_document(client, module, module.params["name"]),
    )


if __name__ == "__main__":
    main()
