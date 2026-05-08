# cloudwatchlogs\_log\_group

Manage aws cloudwatchlogs log groups

## Requirements

None

## Role Variables

    cloudwatchlogs_log_group_async: 300
    cloudwatchlogs_log_group_batch: 10
    cloudwatchlogs_log_group_delay: 3
    cloudwatchlogs_log_group_list: []
    cloudwatchlogs_log_group_poll: 0
    cloudwatchlogs_log_group_retries: 100

## Return Values

None

## Dependencies

* [kms\_key\_info](../kms_key_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.cloudwatchlogs_log_group
          cloudwatchlogs_log_group_list:
            - name: molecule-00
              retention: 30
            - name: molecule-01
              retention: 60
            - name: molecule-02
              retention: 120
