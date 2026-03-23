# aws\_credentials\_info

Gather information about aws credentials

## Requirements

None

## Role Variables

    aws_credentials_info_file: ~/.aws/credentials
    aws_credentials_info_keys:
      - aws_access_key_id
      - aws_secret_access_key
      - aws_security_token
      - aws_session_token
    aws_credentials_info_profile: default

## Return Values

    _aws_credentials_info_aws_access_key_id
    _aws_credentials_info_aws_secret_access_key
    _aws_credentials_info_aws_security_token
    _aws_credentials_info_aws_session_token
    _aws_credentials_info_{{ key }}

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.aws_credentials_info
