# iam\_user

Manage aws iam users

## Requirements

None

## Role Variables

    iam_user_async: 120
    iam_user_batch: 10
    iam_user_delay: 3
    iam_user_list: []
    iam_user_poll: 0
    iam_user_retries: 40

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_user
          iam_user_list:
            - name: molecule-admin
              purge_policies: true
            - name: molecule-kopia
              purge_policies: true
            - name: molecule-molecule
              purge_policies: true
