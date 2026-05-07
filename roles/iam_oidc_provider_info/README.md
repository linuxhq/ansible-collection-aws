# iam\_oidc\_provider\_info

Gather information about aws identity and access management oidc providers

## Requirements

None

## Role Variables

    iam_oidc_provider_info_arn: null
    iam_oidc_provider_info_url: null

## Return Values

    _iam_oidc_provider_info_dict
    _iam_oidc_provider_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_oidc_provider_info
          iam_oidc_provider_info_url: https://token.actions.githubusercontent.com
