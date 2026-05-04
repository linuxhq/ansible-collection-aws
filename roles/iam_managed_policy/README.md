# iam\_managed\_policy

Manage aws identity and access management policies

## Requirements

None

## Role Variables

    iam_managed_policy_async: 300
    iam_managed_policy_batch: 10
    iam_managed_policy_delay: 3
    iam_managed_policy_list: []
    iam_managed_policy_poll: 0
    iam_managed_policy_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_managed_policy
          iam_managed_policy_list:
            - name: molecule-admin
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action: '*'
                    Resource: '*'

            - name: molecule-s3
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action: 's3:*'
                    Resource: '*'
