# ec2\_vpc\_vpn

Manage aws virtual private cloud vpn connections

## Requirements

None

## Role Variables

    ec2_vpc_vpn_async: 600
    ec2_vpc_vpn_batch: 10
    ec2_vpc_vpn_delay: 3
    ec2_vpc_vpn_list: []
    ec2_vpc_vpn_poll: 0
    ec2_vpc_vpn_retries: 200

## Return Values

None

## Dependencies

* [ec2\_customer\_gateway\_info](../ec2_customer_gateway_info)
* [ec2\_transit\_gateway\_info](../ec2_transit_gateway_info)
* [ec2\_vpc\_vgw\_info](../ec2_vpc_vgw_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_vpn
          ec2_vpc_vpn_list:
            - name: molecule-00
              customer_gateway_id:
                "{{ _ec2_customer_gateway_info_dict['molecule-00'].customer_gateway_id }}"
              transit_gateway_id:
                "{{ _ec2_transit_gateway_info_dict['molecule-00'].transit_gateway_id }}"

            - name: molecule-01
              customer_gateway_id:
                "{{ _ec2_customer_gateway_info_dict['molecule-01'].customer_gateway_id }}"
              transit_gateway_id:
                "{{ _ec2_transit_gateway_info_dict['molecule-01'].transit_gateway_id }}"
              static_only: true
              tunnel_options:
                - IKEVersions:
                    - Value: ikev2
                  Phase1EncryptionAlgorithms:
                    - Value: AES256
                  Phase1IntegrityAlgorithms:
                    - Value: SHA2-256
                  Phase1DHGroupNumbers:
                    - Value: 16
                  Phase2EncryptionAlgorithms:
                    - Value: AES256
                  Phase2IntegrityAlgorithms:
                    - Value: SHA2-256
                  Phase2DHGroupNumbers:
                    - Value: 16
                - IKEVersions:
                    - Value: ikev2
                  Phase1EncryptionAlgorithms:
                    - Value: AES256
                  Phase1IntegrityAlgorithms:
                    - Value: SHA2-256
                  Phase1DHGroupNumbers:
                    - Value: 16
                  Phase2EncryptionAlgorithms:
                    - Value: AES256
                  Phase2IntegrityAlgorithms:
                    - Value: SHA2-256
                  Phase2DHGroupNumbers:
                    - Value: 16
