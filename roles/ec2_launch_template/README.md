# ec2\_launch\_template

Manage aws ec2 launch templates

## Requirements

None

## Role Variables

    ec2_launch_template_async: 300
    ec2_launch_template_batch: 10
    ec2_launch_template_delay: 3
    ec2_launch_template_list: []
    ec2_launch_template_poll: 0
    ec2_launch_template_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_launch_template
          ec2_ami_info_list:
            - name: 'AlmaLinux OS 8'
              filters:
                owner-alias: aws-marketplace
                product-code: be714bpjscoj5uvqz0of5mscl
                product-code.type: marketplace
                is-public: true
                virtualization-type: hvm
          ec2_launch_template_list:
            - template_name: linuxhq-al8
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.medium
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['linuxhq-ssh'].group_id }}"
