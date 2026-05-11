# iam\_oidc\_provider

Manage aws identity and access management oidc providers

## Requirements

None

## Role Variables

    iam_oidc_provider_async: 300
    iam_oidc_provider_batch: 10
    iam_oidc_provider_delay: 3
    iam_oidc_provider_list: []
    iam_oidc_provider_poll: 0
    iam_oidc_provider_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_oidc_provider
          iam_oidc_provider_list:
            - name: github-actions
              url: https://token.actions.githubusercontent.com
              client_id_list:
                - sts.amazonaws.com
              thumbprint_list:
                - 6938fd4d98bab03faadb97b34396831e3780aea1
