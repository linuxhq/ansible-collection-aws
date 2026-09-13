# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from ansible.module_utils.common.dict_transformations import (
    camel_dict_to_snake_dict,
    snake_dict_to_camel_dict,
)

# Most Automation inputs use PascalCase; Step Functions uses lower camelCase.
AUTOMATION_ACTIONS = {
    "aws:approve",
    "aws:assertAwsResourceProperty",
    "aws:branch",
    "aws:changeInstanceState",
    "aws:copyImage",
    "aws:createImage",
    "aws:createStack",
    "aws:createTags",
    "aws:deleteImage",
    "aws:deleteStack",
    "aws:executeAutomation",
    "aws:executeAwsApi",
    "aws:executeScript",
    "aws:executeStateMachine",
    "aws:invokeWebhook",
    "aws:invokeLambdaFunction",
    "aws:loop",
    "aws:pause",
    "aws:runCommand",
    "aws:runInstances",
    "aws:sleep",
    "aws:updateVariable",
    "aws:waitForAwsResourceProperty",
}
API_ACTION_FIELDS = {
    "aws:executeAwsApi": {"service", "api"},
    "aws:assertAwsResourceProperty": {"service", "api", "property_selector", "desired_values"},
    "aws:waitForAwsResourceProperty": {"service", "api", "property_selector", "desired_values"},
}
STACK_FIELD_NAMES = {
    "notification_arns": "NotificationARNs",
    "role_arn": "RoleARN",
    "stack_policy_url": "StackPolicyURL",
    "template_url": "TemplateURL",
}


def snake_field(key):
    return next(iter(camel_dict_to_snake_dict({key: None})))


def normalize_action_inputs(content, action, *, snake_case=False, _root=True):
    """Normalize action schema fields without rewriting embedded API requests or data."""
    if isinstance(content, list):
        return [normalize_action_inputs(item, action, snake_case=snake_case, _root=False) for item in content]

    if not isinstance(content, dict):
        return content

    result = {}
    for key, value in content.items():
        snake_key = snake_field(key)
        if _root and action in API_ACTION_FIELDS and snake_key not in API_ACTION_FIELDS[action]:
            # The selected API defines its own casing, structures, and arbitrary maps.
            result[key] = value
            continue

        if snake_case:
            converted_key = snake_key
        elif action in ("aws:createStack", "aws:deleteStack") and snake_key in STACK_FIELD_NAMES:
            converted_key = STACK_FIELD_NAMES[snake_key]
        else:
            converted_key = next(
                iter(snake_dict_to_camel_dict({snake_key: None}, capitalize_first=action != "aws:executeStateMachine"))
            )

        if action == "aws:loop" and _root and snake_key == "steps":
            result[converted_key] = normalize_document_content(value, snake_case=snake_case, _path=("main_steps",))
        elif (
            snake_key in ("input_payload", "payload", "input", "runtime_parameters", "target_maps", "iterators")
            or (action == "aws:runCommand" and snake_key == "parameters")
            or (action == "aws:updateVariable" and snake_key == "value")
            or (action == "aws:invokeWebhook" and snake_key in ("body", "headers"))
        ):
            result[converted_key] = value
        else:
            result[converted_key] = normalize_action_inputs(value, action, snake_case=snake_case, _root=False)

    return result


def normalize_document_content(content, *, document_type=None, snake_case=False, _path=(), _action=None):
    """Convert schema fields while preserving document identifiers and payloads."""
    if document_type in ("ApplicationConfiguration", "ApplicationConfigurationSchema", "CloudFormation"):
        return content

    if isinstance(content, list):
        return [
            normalize_document_content(item, snake_case=snake_case, _path=_path, _action=_action) for item in content
        ]

    if not isinstance(content, dict):
        return content

    if _path == ("main_steps",):
        _action = content.get("action") if isinstance(content.get("action"), str) else None

    result = {}
    for key, value in content.items():
        snake_key = snake_field(key)
        if _path in (("parameters",), ("variables",), ("files",)):
            converted_key = key
        elif snake_case:
            converted_key = snake_key
        elif (
            _path == ("main_steps", "outputs")
            and _action in AUTOMATION_ACTIONS
            and snake_key in ("name", "selector", "type")
        ):
            converted_key = snake_key.capitalize()
        elif _path == ("main_steps", "precondition") and snake_key == "string_equals":
            converted_key = "StringEquals"
        else:
            converted_key = next(iter(snake_dict_to_camel_dict({key: None}, capitalize_first=False)))

        if _path == ("main_steps",) and snake_key == "inputs" and _action in AUTOMATION_ACTIONS:
            result[converted_key] = normalize_action_inputs(value, _action, snake_case=snake_case)
        elif (
            (document_type == "Package" and not _path and snake_key == "packages")
            or snake_key == "input_payload"
            or (
                _path == ("main_steps", "inputs")
                and _action == "aws:runDocument"
                and snake_key == "document_parameters"
            )
            or (len(_path) == 2 and _path[0] in ("parameters", "variables") and snake_key == "default")
        ):
            result[converted_key] = value
        else:
            result[converted_key] = normalize_document_content(
                value, snake_case=snake_case, _path=_path + (snake_key,), _action=_action
            )

    return result
