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
          ec2_launch_template_list:
            - template_name: molecule-el8-nano
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.nano
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el8-micro
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.micro
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el8-small
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.small
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el8-medium
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.medium
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el8-large
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.large
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el8-xlarge
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 8'] }}"
              instance_type: t3.xlarge
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-nano
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.nano
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-micro
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.micro
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-small
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.small
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-medium
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.medium
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-large
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.large
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
            - template_name: molecule-el9-xlarge
              image_id: "{{ _ec2_ami_info_latest['AlmaLinux OS 9'] }}"
              instance_type: t3.xlarge
              security_group_ids:
                - "{{ _ec2_security_group_info_dict['molecule-ssh'].group_id }}"
