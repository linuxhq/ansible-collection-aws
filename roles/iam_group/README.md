# iam\_group

Manage aws iam groups

## Requirements

None

## Role Variables

    iam_group_async: 300
    iam_group_batch: 10
    iam_group_delay: 3
    iam_group_list: []
    iam_group_poll: 0
    iam_group_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_group
          iam_group_list:
            - name: molecule-admin
              managed_policies:
                - AdministratorAccess
              purge_policies: true
              users:
                - molecule-admin

            - name: molecule-kopia
              managed_policies:
                - AmazonS3FullAccess
              purge_policies: true
              users:
                - molecule-kopia

            - name: molecule-molecule
              managed_policies:
                - AmazonEC2FullAccess
                - AmazonVPCReadOnlyAccess
              purge_policies: true
              users:
                - molecule-molecule
