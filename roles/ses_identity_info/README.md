# ses\_identity\_info

Gather information about aws simple email service identities

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

None

## Return Values

    _ses_identity_info_dict
    _ses_identity_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.ses_identity_info
