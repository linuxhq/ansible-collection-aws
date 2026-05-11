# sns\_sms\_attributes

Manage aws simple notification service sms attributes

## Requirements

None

## Role Variables

    sns_sms_attributes_default_sender_id: null
    sns_sms_attributes_default_sms_type: null
    sns_sms_attributes_delivery_status_iam_role: null
    sns_sms_attributes_delivery_status_success_sampling_rate: null
    sns_sms_attributes_monthly_spend_limit: null
    sns_sms_attributes_usage_report_s3_bucket: null

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.sns_sms_attributes
          sns_sms_attributes_default_sms_type: Transactional
          sns_sms_attributes_delivery_status_success_sampling_rate: "10"
          sns_sms_attributes_monthly_spend_limit: "25"
