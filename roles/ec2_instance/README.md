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
          ec2_instance_list:
            - name: molecule-a
              exact_count: 3
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t2.medium
              vpc_subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pvt-a'].id }}"
            - name: molecule-b
              exact_count: 3
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t2.medium
              vpc_subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pvt-b'].id }}"
            - name: molecule-c
              exact_count: 3
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t2.medium
              vpc_subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule-pvt-c'].id }}"
