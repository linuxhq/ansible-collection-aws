# pinpoint\_sms\_voice\_sender\_id\_info

Gather information about aws end user messaging sms sender ids

## Requirements

None

## Role Variables

    pinpoint_sms_voice_sender_id_info_filters: {}
    pinpoint_sms_voice_sender_id_info_max_results: null
    pinpoint_sms_voice_sender_id_info_owner: null
    pinpoint_sms_voice_sender_id_info_sender_ids: []

## Return Values

    _pinpoint_sms_voice_sender_id_info_dict
    _pinpoint_sms_voice_sender_id_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.pinpoint_sms_voice_sender_id_info
