# profile

Manage aws profile config and credentials

## Requirements

None

## Role Variables

    profile_dir: '~/.aws'
    profile_list: []
    profile_no_log: false

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      roles:
        - role: linuxhq.aws.profile
