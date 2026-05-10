# pinpoint\_sms\_voice\_phone\_pool\_info

Gather information about aws end user messaging sms phone pools

## Requirements

None

## Role Variables

    pinpoint_sms_voice_phone_pool_info_filters: {}
    pinpoint_sms_voice_phone_pool_info_max_results: null
    pinpoint_sms_voice_phone_pool_info_owner: SELF
    pinpoint_sms_voice_phone_pool_info_pool_ids: []

## Return Values

    _pinpoint_sms_voice_phone_pool_info_dict
    _pinpoint_sms_voice_phone_pool_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - linuxhq.aws.pinpoint_sms_voice_phone_pool_info
