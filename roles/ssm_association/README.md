# ssm\_association

Manage aws systems manager associations

## Requirements

* [awscli](https://pypi.org/project/awscli)

## Role Variables

    ssm_association_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_association
          ssm_association_list:
            - name: AWS-UpdateSSMAgent
              schedule_expression: 'cron(0 0 * * ? *)'
              targets:
                - Key: InstanceIds
                  Values: ['*']
