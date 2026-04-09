# ssm\_session

Manage aws systems manager session configuration

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    Defaults can be found in [main](main/)

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_session
          ssm_session_kms_key_admins:
            - root
            - role/admin
          ssm_session_kms_key_consumers:
            - role/instance-profile-*
            - role/*ro
            - role/*rw
            - user/molecule
          ssm_session_shell_profile_linux: |-
            cd
