# ssm\_document\_info

Gather information about aws systems manager documents

## Role Variables

    ssm_document_info_document_format: JSON
    ssm_document_info_document_version: null
    ssm_document_info_filters: {}
    ssm_document_info_names: []
    ssm_document_info_version_name: null

## Return Values

    _ssm_document_info_dict
    _ssm_document_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_document_info
          ssm_document_info_names:
            - molecule-command-shell
