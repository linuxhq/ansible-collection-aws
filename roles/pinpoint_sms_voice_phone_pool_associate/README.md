# pinpoint\_sms\_voice\_phone\_pool\_associate

Manage aws end user messaging sms phone pool associations

## Requirements

None

## Role Variables

    pinpoint_sms_voice_phone_pool_associate_async: 300
    pinpoint_sms_voice_phone_pool_associate_batch: 10
    pinpoint_sms_voice_phone_pool_associate_delay: 3
    pinpoint_sms_voice_phone_pool_associate_list: []
    pinpoint_sms_voice_phone_pool_associate_poll: 0
    pinpoint_sms_voice_phone_pool_associate_retries: 100

## Return Values

None

## Dependencies

* [pinpoint\_sms\_voice\_phone\_number\_info](../pinpoint_sms_voice_phone_number_info)
* [pinpoint\_sms\_voice\_phone\_pool\_info](../pinpoint_sms_voice_phone_pool_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.pinpoint_sms_voice_phone_pool_associate
          pinpoint_sms_voice_phone_pool_associate_list:
            - pool_id: "{{ _pinpoint_sms_voice_phone_pool_info_dict['molecule-pinpoint-pool'].pool_id }}"
              iso_country_code: US
              associations:
                - origination_identity: phone-0123456789abcdef0123456789abcdef
                - origination_identity: phone-0123456789abcdef0123456789abcdeg
