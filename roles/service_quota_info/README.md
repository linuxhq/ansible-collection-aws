# service\_quota\_info

Gather information about aws service quotas

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    service_quota_info_list: []

## Return Values

    _service_quota_info_dict
    _service_quota_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.service_quota_info
          service_quota_info_list:
            - service_code: ec2
              quotas:
                - quota_code: L-0263D0A3
                - quota_code: L-1216C47A

            - service_code: iam
              quotas:
                - quota_code: L-0DA4ABF3
                  region: us-east-1

            - service_code: vpc
              quotas:
                - quota_code: L-0EA8095F
