# notifications\_hub

Manage aws notifications hubs

## Requirements

None

## Role Variables

    notifications_hub_async: 300
    notifications_hub_batch: 10
    notifications_hub_delay: 3
    notifications_hub_list: []
    notifications_hub_poll: 0
    notifications_hub_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.notifications_hub
          notifications_hub_list:
            - region: eu-central-1
            - region: us-west-1
