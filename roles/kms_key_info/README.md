# kms\_key\_info

Gather information about key management service keys

## Requirements

None

## Role Variables

    kms_key_info_alias: null
    kms_key_info_filters: {}
    kms_key_info_key_id: null
    kms_key_info_pending_deletion: false

## Return Values

    _kms_key_info_dict
    _kms_key_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.kms_key_info
