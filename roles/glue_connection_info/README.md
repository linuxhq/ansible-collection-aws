# glue\_connection\_info

Gather information about aws glue connections

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _glue_connection_info_dict
    _glue_connection_info_list

## Dependencie

Nones

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.glue_connection_info
