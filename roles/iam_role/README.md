# iam\_role

Manage aws identity and access management roles

## Requirements

None

## Role Variables

    iam_role_async: 300
    iam_role_batch: 10
    iam_role_delay: 3
    iam_role_list: []
    iam_role_poll: 0
    iam_role_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_role
          iam_role_list:
            - name: LinuxHQEKSNodeGroup
              assume_role_policy_document:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      Service: ec2.amazonaws.com
                    Action:
                      - sts:AssumeRole
              managed_policies:
                - AmazonEC2ContainerRegistryReadOnly
                - AmazonEKS_CNI_Policy
                - AmazonEKSWorkerNodePolicy
                - AmazonSSMManagedInstanceCore
                - AmazonS3ReadOnlyAccess
                - CloudWatchAgentServerPolicy
