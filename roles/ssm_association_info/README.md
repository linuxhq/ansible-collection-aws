# ssm\_association\_info

Gather information about aws systems manager associations

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _ssm_association_info_dict
    _ssm_association_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ssm_association_info
