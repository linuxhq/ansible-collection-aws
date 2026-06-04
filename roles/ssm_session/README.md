# ssm\_session

Manage aws systems manager session configuration

## Requirements

None

## Role Variables

Defaults can be found in [here](defaults/main)

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_session
          ssm_session_kms_key_consumers:
            - role/molecule-instance
          ssm_session_shell_profile_linux: cd
