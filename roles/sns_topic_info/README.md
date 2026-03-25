# sns\_topic\_info

Gather information about aws simple notification service topics

## Requirements

None

## Role Variables

None

## Return Values

    _sns_topic_info_dict
    _sns_topic_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.sns_topic_info
