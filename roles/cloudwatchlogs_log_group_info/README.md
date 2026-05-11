# cloudwatchlogs\_log\_group\_info

Gather information about aws cloudwatch logs log groups

## Requirements

None

## Role Variables

    cloudwatchlogs_log_group_info_log_group_name: null

## Return Values

    _cloudwatchlogs_log_group_info_dict
    _cloudwatchlogs_log_group_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.cloudwatchlogs_log_group_info
