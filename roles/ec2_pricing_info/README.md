# ec2\_pricing\_info

Gather information about aws pricing products

## Requirements

None

## Role Variables

    ec2_pricing_info_filters: []
    ec2_pricing_info_format_version: aws_v1
    ec2_pricing_info_max_results: null
    ec2_pricing_info_service_code: AmazonEC2

## Return Values

    _ec2_pricing_info_dict
    _ec2_pricing_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_pricing_info
          ec2_pricing_info_filters:
            - field: instanceType
              value: t3.micro
            - field: regionCode
              value: us-west-2
            - field: operatingSystem
              value: Linux
            - field: tenancy
              value: Shared
