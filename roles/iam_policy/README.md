# iam\_policy

Manage aws identity and access management inline policies

## Requirements

None

## Role Variables

    iam_policy_async: 300
    iam_policy_batch: 10
    iam_policy_delay: 3
    iam_policy_list: []
    iam_policy_poll: 0
    iam_policy_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_policy
          iam_policy_list:
            - iam_name: molecule-ec2
              iam_type: user
              policy_json:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action:
                      - ec2:*
                    Resource:
                      - '*'
              policy_name: MoleculeEc2FullAccess

            - iam_name: molecule-rds
              iam_type: group
              policy_json:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Action:
                      - rds:*
                    Resource:
                      - '*'
              policy_name: MoleculeRdsFullAccess
