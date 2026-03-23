# service\_quota

Manage aws service quotas

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    service_quota_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.service_quota
          service_quota_list:
            - service_code: ec2
              quotas:
                - quota_code: L-0263D0A3
                  value: '10.0'
                - quota_code: L-1216C47A
                  value: '128.0'

            - service_code: iam
              quotas:
                - quota_code: L-0DA4ABF3
                  region: us-east-1
                  value: '20.0'

            - service_code: vpc
              quotas:
                - quota_code: L-0EA8095F
                  value: '125.0'
