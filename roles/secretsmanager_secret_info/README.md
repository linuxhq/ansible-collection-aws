# secretsmanager\_secret\_info

Gather information about aws secrets manager secrets

## Requirements

None

## Role Variables

    secretsmanager_secret_info_list: []
    secretsmanager_secret_info_on_deleted: error
    secretsmanager_secret_info_on_denied: error
    secretsmanager_secret_info_on_missing: error

## Return Values

    _secretsmanager_secret_info_dict
    _secretsmanager_secret_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.secretsmanager_secret_info
          secretsmanager_secret_info_list:
            - name: molecule-secret-1
            - name: molecule-secret-2
