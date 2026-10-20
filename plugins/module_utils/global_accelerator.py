# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible_collections.linuxhq.aws.plugins.module_utils.tags import require_valid_tag_list


def validate_tag_list(module, tags):
    """Validate a Global Accelerator tag list, which must also have non-empty tag keys."""
    msg = "Global Accelerator returned invalid tags"
    require_valid_tag_list(module, tags, msg)
    if any(not tag["Key"] for tag in tags):
        module.fail_json(msg=msg)

    return tags
