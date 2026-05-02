# ec2\_instance\_metadata\_info

Gather information about aws ec2 instance metadata defaults

## Requirements

None

## Role Variables

    ec2_instance_metadata_info_regions:
      - us-east-1

## Return Values

    _ec2_instance_metadata_info_dict
    _ec2_instance_metadata_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance_metadata_info
          ec2_instance_metadata_info_regions:
            "{{ (_aws_region_info_list |
                map(attribute='region_name')) |
                d(['us-east-1']) }}"
