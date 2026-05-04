# ssm\_document\_info

Gather information about aws systems manager documents

## Role Variables

    ssm_document_info_name: molecule-command-shell

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
          ssm_document_info_name: molecule-command-shell
