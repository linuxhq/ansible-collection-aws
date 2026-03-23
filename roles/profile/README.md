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
          profile_list:
            - name: linuxhq
              config:
                output: json
                region: us-east-1
              credentials:
                aws_access_key_id:
                  "{{ lookup('ansible.builtin.ini',
                             'aws_access_key_id',
                             file='~/.aws/credentials',
                             section='linuxhq') }}"
                aws_secret_access_key:
                  "{{ lookup('ansible.builtin.ini',
                             'aws_secret_access_key',
                             file='~/.aws/credentials',
                             section='linuxhq') }}"
