# ssm\_association\_info

Gather information about aws systems manager associations

## Role Variables

    ssm_association_info_filters: {}

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
