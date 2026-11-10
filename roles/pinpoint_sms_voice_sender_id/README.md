# pinpoint\_sms\_voice\_sender\_id

Manage aws end user messaging sms sender ids

## Requirements

None

## Role Variables

    pinpoint_sms_voice_sender_id_async: 300
    pinpoint_sms_voice_sender_id_batch: 10
    pinpoint_sms_voice_sender_id_delay: 3
    pinpoint_sms_voice_sender_id_list: []
    pinpoint_sms_voice_sender_id_poll: 0
    pinpoint_sms_voice_sender_id_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.pinpoint_sms_voice_sender_id
          pinpoint_sms_voice_sender_id_list:
            - sender_id: MOLECULE
              iso_country_code: DE
              message_types:
                - TRANSACTIONAL
