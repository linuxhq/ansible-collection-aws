# lambda\_info

Gather information about aws lambda functions

## Requirements

None

## Role Variables

    lambda_info_event_source_arn: null
    lambda_info_function_name: null
    lambda_info_query: null

## Return Values

    _lambda_info_dict
    _lambda_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.lambda
