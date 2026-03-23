# iam\_password\_policy

Manage aws identity and access management password policy

## Requirements

None

## Role Variables

    iam_password_policy_allow_pw_change: false
    iam_password_policy_min_pw_length: 6
    iam_password_policy_pw_expire: false
    iam_password_policy_pw_max_age: 0
    iam_password_policy_pw_reuse_prevent: 0
    iam_password_policy_require_lowercase: false
    iam_password_policy_require_numbers: false
    iam_password_policy_require_symbols: false
    iam_password_policy_require_uppercase: false
    iam_password_policy_state: present

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.iam_password_policy
          iam_password_policy_allow_pw_change: true
          iam_password_policy_min_pw_length: 12
          iam_password_policy_pw_expire: false
          iam_password_policy_pw_max_age: 90
          iam_password_policy_pw_reuse_prevent: 24
          iam_password_policy_require_lowercase: true
          iam_password_policy_require_numbers: true
          iam_password_policy_require_symbols: true
          iam_password_policy_require_uppercase: true
