# ec2\_instance

Manage aws ec2 instances

## Requirements

None

## Role Variables

    ec2_instance_async: 600
    ec2_instance_batch: 10
    ec2_instance_delay: 3
    ec2_instance_list: []
    ec2_instance_poll: 0
    ec2_instance_retries: 300

## Return Values

None

## Dependencies

* [ec2\_ami\_info](../ec2_ami_info)
* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_instance
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 9'
              filters:
                owner-alias: aws-marketplace
                product-code: 3kukoxmnoighcsbjd0u4nq9ds
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm

          ec2_instance_list:
            - name: linuxhq-1
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.small
              vpc_subnet_id: "{{ _ec2_vpc_subnet_info_dict['linuxhq-pvt-a'].id }}"
