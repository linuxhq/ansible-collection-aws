# pinpoint\_sms\_voice\_phone\_pool

Manage aws end user messaging sms phone pools

## Requirements

None

## Role Variables

    pinpoint_sms_voice_phone_pool_async: 300
    pinpoint_sms_voice_phone_pool_batch: 10
    pinpoint_sms_voice_phone_pool_delay: 3
    pinpoint_sms_voice_phone_pool_list: []
    pinpoint_sms_voice_phone_pool_poll: 0
    pinpoint_sms_voice_phone_pool_retries: 100

## Return Values

None

## Dependencies

* [pinpoint\_sms\_voice\_phone\_number\_info](../pinpoint_sms_voice_phone_number_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.pinpoint_sms_voice_phone_pool
          pinpoint_sms_voice_phone_pool_list:
            - name: molecule-pinpoint-pool
              origination_identity: phone-0123456789abcdef0123456789abcdef
              iso_country_code: US
              message_type: TRANSACTIONAL
