# pinpoint\_sms\_voice\_phone\_number

Manage aws end user messaging sms phone numbers

## Requirements

None

## Role Variables

    pinpoint_sms_voice_phone_number_async: 300
    pinpoint_sms_voice_phone_number_batch: 10
    pinpoint_sms_voice_phone_number_delay: 3
    pinpoint_sms_voice_phone_number_list: []
    pinpoint_sms_voice_phone_number_poll: 0
    pinpoint_sms_voice_phone_number_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.pinpoint_sms_voice_phone_number
          pinpoint_sms_voice_phone_number_list:
            - name: molecule-pinpoint-simulator
              iso_country_code: US
              message_type: TRANSACTIONAL
              number_capabilities:
                - SMS
              number_type: SIMULATOR
