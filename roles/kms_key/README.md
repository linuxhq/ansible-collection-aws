# kms\_key

Manage aws key management service keys

## Requirements

None

## Role Variables

    kms_key_async: 300
    kms_key_batch: 10
    kms_key_delay: 3
    kms_key_list: []
    kms_key_poll: 0
    kms_key_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.kms_key
          kms_key_list:
            - name: molecule-root
              pending_window: 7
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS: "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action: kms:*
                    Resource: '*'
            - name: molecule-admin
              pending_window: 7
              policy:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal:
                      AWS: "arn:aws:iam::{{ _aws_caller_info_account }}:root"
                    Action: kms:*
                    Resource: '*'
                  - Effect: Allow
                    Principal:
                      AWS: '*'
                    Action: kms:*
                    Resource: '*'
                    Condition:
                      ArnEquals:
                        aws:PrincipalArn:
                          - "arn:aws:iam::{{ _aws_caller_info_account }}:role/admin"
