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

from ansible_collections.amazon.aws.plugins.module_utils.modules import AnsibleAWSModule
from ansible_collections.linuxhq.aws.plugins.module_utils.ssm import (
    get_document,
)


def main():
    module = AnsibleAWSModule(
        argument_spec={"name": {"required": True, "type": "str"}},
        supports_check_mode=True,
    )
    client = module.client("ssm")

    module.exit_json(
        changed=False,
        document=get_document(
            client,
            module,
            module.params["name"],
            missing_document={},
            fail_on_invalid_content=False,
        ),
    )


if __name__ == "__main__":
    main()
