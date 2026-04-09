# iam\_instance\_profile

Manage aws iam instance profiles

## Requirements

None

## Role Variables

    iam_instance_profile_async: 300
    iam_instance_profile_batch: 10
    iam_instance_profile_delay: 3
    iam_instance_profile_list: []
    iam_instance_profile_poll: 0
    iam_instance_profile_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_instance_profile
          iam_instance_profile_list:
            - name: molecule-instance-profile-ec2
              role: molecule-role-ec2
            - name: molecule-instance-profile-vpc
              role: molecule-role-vpc
