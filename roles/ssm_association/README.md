# ssm\_association

Manage aws systems manager associations

## Requirements

None

## Role Variables

    ssm_association_async: 300
    ssm_association_batch: 10
    ssm_association_delay: 3
    ssm_association_list: []
    ssm_association_poll: 0
    ssm_association_retries: 100

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
                - key: InstanceIds
                  values: ['*']
