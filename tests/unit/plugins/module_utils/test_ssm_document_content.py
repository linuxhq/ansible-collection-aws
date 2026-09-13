import copy

import pytest

from ansible_collections.linuxhq.aws.plugins.module_utils.ssm_document import normalize_document_content


@pytest.mark.parametrize(
    "action,inputs",
    [
        ("aws:approve", {"Approvers": ["arn:aws:iam::123456789012:user/reviewer"], "MinRequiredApprovals": 1}),
        (
            "aws:assertAwsResourceProperty",
            {
                "Service": "ec2",
                "Api": "DescribeInstances",
                "InstanceIds": ["i-example"],
                "PropertySelector": "$.State",
                "DesiredValues": ["running"],
            },
        ),
        (
            "aws:branch",
            {
                "Choices": [
                    {
                        "NextStep": "done",
                        "And": [
                            {"Variable": "{{step.Value}}", "StringEquals": "yes"},
                            {"Not": {"Variable": "{{step.Other}}", "BooleanEquals": False}},
                        ],
                    }
                ],
                "Default": "retry",
            },
        ),
        ("aws:changeInstanceState", {"InstanceIds": ["i-example"], "CheckStateOnly": True, "DesiredState": "running"}),
        (
            "aws:copyImage",
            {
                "SourceImageId": "ami-example",
                "SourceRegion": "us-east-1",
                "ImageName": "copy",
                "KmsKeyId": "alias/example",
            },
        ),
        ("aws:createImage", {"InstanceId": "i-example", "ImageName": "image", "NoReboot": True}),
        (
            "aws:createStack",
            {
                "StackName": "example",
                "TemplateURL": "https://example.com/template",
                "RoleARN": "arn:role",
                "NotificationARNs": ["arn:topic"],
                "StackPolicyURL": "https://example.com/policy",
                "Parameters": [{"ParameterKey": "MyParam", "ParameterValue": "value"}],
            },
        ),
        ("aws:createTags", {"ResourceIds": ["i-example"], "Tags": [{"Key": "MyKey", "Value": "value"}]}),
        ("aws:deleteImage", {"ImageId": "ami-example", "DeleteAssociatedSnapshots": True}),
        ("aws:deleteStack", {"StackName": "example", "RoleARN": "arn:role"}),
        (
            "aws:executeAutomation",
            {
                "DocumentName": "child",
                "RuntimeParameters": {"MyParam": ["one"], "my_param": ["two"]},
                "TargetMaps": [{"MyParam": ["resource"]}],
            },
        ),
        (
            "aws:executeAwsApi",
            {
                "Service": "ssm",
                "Api": "SendCommand",
                "DocumentName": "child",
                "Parameters": {"MyParam": ["one"], "my_param": ["two"]},
            },
        ),
        (
            "aws:executeScript",
            {
                "Runtime": "python3.11",
                "Handler": "handler",
                "Script": "def handler(events, context): return events",
                "InputPayload": {"MyKey": 1, "my_key": 2},
            },
        ),
        ("aws:executeStateMachine", {"stateMachineArn": "arn:machine", "input": '{"MyKey": 1}', "name": "example"}),
        ("aws:invokeWebhook", {"IntegrationName": "example", "Body": '{"MyKey": 1}'}),
        ("aws:invokeLambdaFunction", {"FunctionName": "function", "Payload": '{"MyKey": 1}'}),
        (
            "aws:loop",
            {
                "Iterators": ["one"],
                "IteratorDataType": "String",
                "Steps": [{"name": "delay", "action": "aws:sleep", "inputs": {"Duration": "PT1S"}}],
            },
        ),
        ("aws:pause", {}),
        (
            "aws:runCommand",
            {
                "DocumentName": "child",
                "Parameters": {"MyParam": ["one"], "my_param": ["two"]},
                "CloudWatchOutputConfig": {"CloudWatchLogGroupName": "group", "CloudWatchOutputEnabled": True},
            },
        ),
        (
            "aws:runInstances",
            {
                "ImageId": "ami-example",
                "InstanceType": "t3.micro",
                "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 10, "VolumeType": "gp3"}}],
            },
        ),
        ("aws:sleep", {"Duration": "PT1S"}),
        ("aws:updateVariable", {"Name": "variable:MyVariable", "Value": {"MyKey": "one", "my_key": "two"}}),
        (
            "aws:waitForAwsResourceProperty",
            {
                "Service": "rds",
                "Api": "DescribeDBInstances",
                "DBInstanceIdentifier": "example",
                "PropertySelector": "$.DBInstances[0].DBInstanceStatus",
                "DesiredValues": ["available"],
            },
        ),
    ],
)
def test_automation_actions_round_trip_without_mutating_input(action, inputs):
    native = {
        "schemaVersion": "0.3",
        "mainSteps": [
            {
                "name": "step",
                "action": action,
                "maxAttempts": 2,
                "inputs": inputs,
                "outputs": [{"Name": "Result", "Selector": "$.Value", "Type": "String"}],
            }
        ],
    }
    original = copy.deepcopy(native)
    normalized = normalize_document_content(native, snake_case=True)
    assert normalized["main_steps"][0]["outputs"] == [{"name": "Result", "selector": "$.Value", "type": "String"}]
    assert normalize_document_content(normalized) == original
    assert normalize_document_content(native) == original
    assert native == original


def test_api_request_fields_preserve_service_specific_case_and_map_keys():
    native = {
        "schemaVersion": "0.3",
        "mainSteps": [
            {
                "name": "run",
                "action": "aws:executeAwsApi",
                "inputs": {
                    "Service": "dynamodb",
                    "Api": "PutItem",
                    "TableName": "table",
                    "Item": {"MyKey": {"S": "one"}, "my_key": {"S": "two"}},
                },
            },
            {
                "name": "logs",
                "action": "aws:executeAwsApi",
                "inputs": {
                    "Service": "logs",
                    "Api": "CreateLogGroup",
                    "logGroupName": "group",
                    "tags": {"MyKey": "one", "my_key": "two"},
                },
            },
        ],
    }
    normalized = normalize_document_content(native, snake_case=True)
    assert normalized["main_steps"][0]["inputs"]["Item"] == native["mainSteps"][0]["inputs"]["Item"]
    assert normalized["main_steps"][1]["inputs"]["logGroupName"] == "group"
    assert normalize_document_content(normalized) == native


def test_snake_case_loop_restores_nested_action_and_branch_fields():
    content = {
        "schema_version": "0.3",
        "main_steps": [
            {
                "name": "loop",
                "action": "aws:loop",
                "inputs": {
                    "steps": [
                        {
                            "name": "api",
                            "action": "aws:executeAwsApi",
                            "inputs": {
                                "service": "ec2",
                                "api": "DescribeInstances",
                                "InstanceIds": ["i-example"],
                            },
                            "outputs": [{"name": "State", "selector": "$.State", "type": "String"}],
                        }
                    ],
                    "loop_condition": {"variable": "{{api.State}}", "string_equals": "pending"},
                    "max_iterations": 2,
                },
            }
        ],
    }
    result = normalize_document_content(content)["mainSteps"][0]["inputs"]
    assert result["LoopCondition"] == {"Variable": "{{api.State}}", "StringEquals": "pending"}
    step = result["Steps"][0]
    assert step["inputs"] == {"Service": "ec2", "Api": "DescribeInstances", "InstanceIds": ["i-example"]}
    assert step["outputs"] == [{"Name": "State", "Selector": "$.State", "Type": "String"}]


def test_script_attachment_names_are_preserved():
    content = {"schemaVersion": "0.3", "files": {"My_script.py": {"checksums": {"sha256": "example"}}}}
    result = normalize_document_content(content, snake_case=True)
    assert result["files"] == content["files"]
    assert normalize_document_content(result) == content


@pytest.mark.parametrize("container", ["parameters", "variables"])
@pytest.mark.parametrize("snake_case", [False, True])
def test_action_and_inputs_identifiers_do_not_set_step_context(container, snake_case):
    definitions = {
        "action": {"type": "String", "default": "hello"},
        "inputs": {"type": "String", "default": "world"},
        "outputs": {"type": "String", "default": "result"},
    }
    content = {
        "schemaVersion": "0.3",
        container: definitions,
        "mainSteps": [
            {
                "name": "run",
                "action": "aws:executeStateMachine",
                "inputs": {"stateMachineArn": "arn:machine", "input": "{}"},
            }
        ],
    }
    result = normalize_document_content(content, snake_case=snake_case)
    assert result[container] == definitions
    assert normalize_document_content(result) == content


def test_command_precondition_uses_aws_operator_casing():
    content = {
        "schemaVersion": "2.2",
        "mainSteps": [
            {
                "name": "run",
                "action": "aws:runShellScript",
                "precondition": {"StringEquals": ["platformType", "Linux"]},
                "inputs": {"runCommand": ["echo hello"]},
            }
        ],
    }
    result = normalize_document_content(content, snake_case=True)
    assert result["main_steps"][0]["precondition"] == {"string_equals": ["platformType", "Linux"]}
    assert normalize_document_content(result) == content


def test_nested_loop_state_machine_uses_its_own_action_context():
    content = {
        "schema_version": "0.3",
        "main_steps": [
            {
                "name": "outer",
                "action": "aws:loop",
                "inputs": {
                    "steps": [
                        {
                            "name": "inner",
                            "action": "aws:loop",
                            "inputs": {
                                "steps": [
                                    {
                                        "name": "run",
                                        "action": "aws:executeStateMachine",
                                        "inputs": {
                                            "state_machine_arn": "arn:machine",
                                            "input": "{}",
                                            "name": "example",
                                        },
                                        "outputs": [{"name": "Result", "selector": "$.output", "type": "String"}],
                                    }
                                ],
                                "iterators": ["one"],
                            },
                        }
                    ],
                    "iterators": ["one"],
                },
            }
        ],
    }
    result = normalize_document_content(content)
    step = result["mainSteps"][0]["inputs"]["Steps"][0]["inputs"]["Steps"][0]
    assert step["inputs"] == {"stateMachineArn": "arn:machine", "input": "{}", "name": "example"}
    assert step["outputs"] == [{"Name": "Result", "Selector": "$.output", "Type": "String"}]
    assert normalize_document_content(result, snake_case=True) == content


@pytest.mark.parametrize("snake_case", [False, True])
def test_package_platform_and_architecture_names_are_preserved(snake_case):
    packages = {"amazon": {"_any": {"x86_64": {"file": "test.zip"}}}}
    result = normalize_document_content(
        {"schemaVersion": "2.0", "packages": packages}, document_type="Package", snake_case=snake_case
    )
    assert result["packages"] == packages


@pytest.mark.parametrize("snake_case", [False, True])
def test_cloudformation_content_preserves_schema_and_resource_identifiers(snake_case):
    content = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Resources": {"MyBucket": {"Type": "AWS::S3::Bucket", "Properties": {"BucketName": "example-bucket"}}},
        "Outputs": {"BucketArn": {"Value": {"Fn::GetAtt": ["MyBucket", "Arn"]}}},
    }
    assert normalize_document_content(content, document_type="CloudFormation", snake_case=snake_case) == content


@pytest.mark.parametrize("snake_case", [False, True])
@pytest.mark.parametrize("parameters", [{"MyParam": "first", "myParam": "second"}, '{"MyParam":"first"}'])
def test_composite_document_parameters_are_preserved(snake_case, parameters):
    content = {
        "schemaVersion": "2.2",
        "mainSteps": [
            {
                "action": "aws:runDocument",
                "name": "child",
                "inputs": {
                    "documentType": "SSMDocument",
                    "documentPath": "ChildDocument",
                    "documentParameters": parameters,
                },
            }
        ],
    }
    original = copy.deepcopy(content)
    result = normalize_document_content(content, document_type="Command", snake_case=snake_case)
    steps_key = "main_steps" if snake_case else "mainSteps"
    parameters_key = "document_parameters" if snake_case else "documentParameters"
    assert result[steps_key][0]["inputs"][parameters_key] == parameters
    assert normalize_document_content(result, document_type="Command") == original
    assert content == original
