# ec2\_key

Manage aws ec2 keys

## Requirements

None

## Role Variables

    ec2_key_async: 300
    ec2_key_batch: 10
    ec2_key_delay: 3
    ec2_key_list: []
    ec2_key_poll: 0
    ec2_key_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_key
          ec2_key_list:
            - name: linuxhq
              key_material: "{{ openssh_key_pub }}"
