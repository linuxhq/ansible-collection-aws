# glue\_connection

Manage aws glue connections

## Requirements

None

## Role Variables

    glue_connection_async: 300
    glue_connection_batch: 10
    glue_connection_delay: 3
    glue_connection_list: []
    glue_connection_poll: 0
    glue_connection_retries: 100

## Return Values

None

## Dependencies

* [ec2\_security\_group\_info](../ec2_security_group_info)
* [ec2\_vpc\_subnet\_info](../ec2_vpc_subnet_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.glue_connection
          glue_connection_list:
            - name: molecule
              availability_zone: us-east-1a
              connection_properties:
                KAFKA_SSL_ENABLED: 'false'
              connection_type: NETWORK
              security_groups:
                - "{{ _ec2_security_group_info_dict['molecule-rds'].group_id }}"
              subnet_id: "{{ _ec2_vpc_subnet_info_dict['molecule'].id }}"
