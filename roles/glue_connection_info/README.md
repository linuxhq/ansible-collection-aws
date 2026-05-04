# glue\_connection\_info

Gather information about aws glue connections

## Role Variables

None

## Return Values

    _glue_connection_info_dict
    _glue_connection_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.glue_connection_info
