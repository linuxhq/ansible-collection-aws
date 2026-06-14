# pinpoint\_sms\_voice\_phone\_number\_info

Gather information about aws end user messaging sms phone numbers

## Requirements

None

## Role Variables

    pinpoint_sms_voice_phone_number_info_filters: {}
    pinpoint_sms_voice_phone_number_info_max_results: null
    pinpoint_sms_voice_phone_number_info_owner: null
    pinpoint_sms_voice_phone_number_info_phone_number_ids: []

## Return Values

    _pinpoint_sms_voice_phone_number_info_dict
    _pinpoint_sms_voice_phone_number_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.pinpoint_sms_voice_phone_number_info
