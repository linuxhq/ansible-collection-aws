# awscli

Manage presence of awscli in a virtual environment

## Requirements

None

## Role Variables

    awscli_become: true
    awscli_path: /opt/awscli
    awscli_requirements:
      - awscli
      - botocore
      - boto3

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      roles:
        - linuxhq.aws.awscli
