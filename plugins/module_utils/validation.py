# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


def require_non_blank(module, value, option):
    """Fail when a string, or any entry of a list, is empty or only whitespace.

    None, an unset option, passes; a caller that counts None as blank passes value or "" instead.
    """
    if isinstance(value, list):
        if any(not entry.strip() for entry in value):
            module.fail_json(msg=f"{option} must not contain empty entries")
    elif value is not None and not value.strip():
        module.fail_json(msg=f"{option} must not be empty")
