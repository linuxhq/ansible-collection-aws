# ses\_sandbox\_info

Gather information about aws simple email service account details

## Requirements

None

## Role Variables

None

## Return Values

    _ses_sandbox_info_dict

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ses_sandbox_info
