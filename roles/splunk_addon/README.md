# splunk\_addon

Manage splunk addon dependencies

## Requirements

None

## Role Variables

    splunk_addon_bucket_name: splunk-addon
    splunk_addon_cloudtrail_name: splunk-addon
    splunk_addon_region: us-east-1
    splunk_addon_iam_managed_policies:
      - CloudWatchReadOnlyAccess
    splunk_addon_iam_policy:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Action:
            - iam:CreateAccessKey
            - iam:DeleteAccessKey
            - iam:GetUser
            - iam:ListAccessKeys
            - iam:UpdateAccessKey
          Resource:
            - 'arn:aws:iam::*:user/${aws:username}'
        - Effect: Allow
          Action:
            - sqs:DeleteMessage
            - sqs:ReceiveMessage
          Resource:
            - "arn:aws:sqs:*:{{ __splunk_addon_account }}:{{ splunk_addon_sqs_queue_name }}"
        - Effect: Allow
          Action:
            - s3:GetObject
          Resource:
            - "arn:aws:s3:::{{ __splunk_addon_account }}-{{ splunk_addon_bucket_name }}/*"
    splunk_addon_iam_policy_name: splunk-addon
    splunk_addon_iam_user_name: splunk-addon
    splunk_addon_kms_key_name: splunk-addon
    splunk_addon_sns_topic_name: splunk-addon
    splunk_addon_sqs_queue_name: splunk-addon
    splunk_addon_state: present
    splunk_addon_tags: {}

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.splunk_addon
