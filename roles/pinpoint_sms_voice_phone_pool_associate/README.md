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

Each `pinpoint_sms_voice_phone_pool_associate_list` item takes these keys:

| Key                                   | Required | Description                                                                   |
| ------------------------------------- | -------- | ----------------------------------------------------------------------------- |
| `pool_id`                             | yes      | ID or ARN of the phone pool.                                                  |
| `iso_country_code`                    | yes      | Two-character ISO country code of the origination identities.                 |
| `associations`                        | yes      | Origination identities to manage in the pool.                                 |
| `associations[].origination_identity` | yes      | Phone number or sender ID, as an ID or ARN.                                   |
| `associations[].state`                | no       | `present` (default) or `absent`.                                              |
| `associations[].client_token`         | no       | Idempotency token for this association; use a new token for each association. |

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
                  client_token: molecule-pinpoint-association-1
                - origination_identity: phone-0123456789abcdef0123456789abcdeg
