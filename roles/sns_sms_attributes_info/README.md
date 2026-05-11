# sns\_sms\_attributes\_info

Gather information about aws simple notification service sms attributes

## Requirements

None

## Role Variables

    sns_sms_attributes_info_attributes: []

## Return Values

    _sns_sms_attributes_info_dict

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.sns_sms_attributes_info
          sns_sms_attributes_info_attributes:
            - DefaultSMSType
            - MonthlySpendLimit
