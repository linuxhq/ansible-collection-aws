# glue\_connection\_info

Gather information about aws glue connections

## Role Variables

    glue_connection_info_apply_override_for_compute_environment: null
    glue_connection_info_catalog_id: null
    glue_connection_info_filters: {}
    glue_connection_info_hide_password: true
    glue_connection_info_name: null

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
