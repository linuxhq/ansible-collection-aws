# secretsmanager\_secret

Manage aws secrets manager secrets

## Requirements

None

## Role Variables

    secretsmanager_secret_async: 300
    secretsmanager_secret_batch: 10
    secretsmanager_secret_delay: 3
    secretsmanager_secret_list: []
    secretsmanager_secret_poll: 0
    secretsmanager_secret_retries: 100

## Return Values

None

## Dependencies

* [rds\_instance\_info](../rds_instance_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.secretsmanager_secret
          secretsmanager_secret_list:
            - name: molecule-secret-1
              secret:
                - key: molecule-secret-1
                  value: WnvpxzicuneCE7PM7upC7aVNFwYoz7wE
            - name: molecule-secret-2
              secret:
                - key: molecule-secret-2
                  value: JUJMm9adCgL7FPtF7qiuHjyXYne7ivbX
                - key: molecule-secret-2a
                  value: ggfiFwtaauCRwwNfxJUE3oRjoHr3ETLL
