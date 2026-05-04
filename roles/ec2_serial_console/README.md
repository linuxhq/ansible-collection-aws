# ec2\_serial\_console

Manage aws ec2 serial console access

## Requirements

None

## Role Variables

    ec2_serial_console_async: 300
    ec2_serial_console_batch: 10
    ec2_serial_console_delay: 3
    ec2_serial_console_poll: 0
    ec2_serial_console_regions:
      - us-east-1
    ec2_serial_console_retries: 100
    ec2_serial_console_state: present

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_serial_console
          ec2_serial_console_regions:
            "{{ (_aws_region_info_list |
                map(attribute='region_name')) |
                d(['us-east-1']) }}"
