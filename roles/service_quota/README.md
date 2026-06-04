# service\_quota

Manage aws service quotas

## Requirements

None

## Role Variables

    service_quota_async: 300
    service_quota_batch: 10
    service_quota_delay: 3
    service_quota_list: []
    service_quota_poll: 0
    service_quota_retries: 100

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
                  value: '15.0'
                - quota_code: L-1216C47A
                  value: '130.0'
            - service_code: iam
              quotas:
                - quota_code: L-0DA4ABF3
                  region: us-east-1
                  value: '25.0'
            - service_code: vpc
              quotas:
                - quota_code: L-0EA8095F
                  value: '130.0'
