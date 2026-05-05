# account\_region

Manage opt-in status of aws account regions

## Requirements

None

## Role Variables

    account_region_async: 3600
    account_region_batch: 10
    account_region_delay: 30
    account_region_list: []
    account_region_poll: 0
    account_region_retries: 120
    account_region_wait: true

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.account_region
          account_region_list:
            - name: af-south-1
            - name: ap-east-1
            - name: ca-west-1
