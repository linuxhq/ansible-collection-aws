# ec2\_eip

Manage aws ec2 elastic ip addresses

## Requirements

None

## Role Variables

    ec2_eip_async: 300
    ec2_eip_batch: 10
    ec2_eip_delay: 3
    ec2_eip_list: []
    ec2_eip_poll: 0
    ec2_eip_retries: 100

## Return Values

None

## Dependencies

* [ec2\_instance\_info](../ec2_instance_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_eip
          ec2_eip_list:
            - name: molecule-eip-01
            - name: molecule-eip-02
            - name: molecule-eip-03
            - name: molecule-eip-04
            - name: molecule-eip-05
