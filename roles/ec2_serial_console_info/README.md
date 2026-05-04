# ec2\_serial\_console\_info

Gather information about aws ec2 serial console access

## Requirements

None

## Role Variables

    ec2_serial_console_info_regions:
      - us-east-1

## Return Values

    _ec2_serial_console_info_dict
    _ec2_serial_console_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_serial_console_info
          ec2_serial_console_info_regions:
            "{{ (_aws_region_info_list |
                map(attribute='region_name')) |
                d(['us-east-1']) }}"
