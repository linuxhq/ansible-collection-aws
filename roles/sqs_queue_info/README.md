# sqs\_queue\_info

Gather information about aws simple queue service queues

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _sqs_queue_info_dict
    _sqs_queue_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.sqs_queue_info
