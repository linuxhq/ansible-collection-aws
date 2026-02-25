# elb\_target\_group

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws elastic load balancer target groups

## Requirements

None

## Role Variables

    elb_target_group_async: 300
    elb_target_group_batch: 10
    elb_target_group_delay: 3
    elb_target_group_list: []
    elb_target_group_poll: 0
    elb_target_group_retries: 100

## Return Values

None

## Dependencies

* [linuxhq.aws.ec2\_instance\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_instance_info)
* [linuxhq.aws.ec2\_vpc\_net\_info](https://github.com/linuxhq/ansible-collection-aws/tree/main/roles/ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.elb_target_group
          elb_target_group_list:
            - name: molecule-http-8080
              health_check_interval: 10
              health_check_path: /healthcheck
              health_check_port: 8080
              health_check_protocol: http
              healthy_threshold_count: 3
              port: 8080
              protocol: http
              stickiness_enabled: true
              target_type: instance
              targets:
                - Id: "{{ _ec2_instance_info_dict['molecule-1'].instance_id }}"
                  Port: 8080
                - Id: "{{ _ec2_instance_info_dict['molecule-2'].instance_id }}"
                  Port: 8080
                - Id: "{{ _ec2_instance_info_dict['molecule-3'].instance_id }}"
                  Port: 8080
              unhealthy_threshold_count: 3
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

            - name: molecule-http-8081
              health_check_interval: 10
              health_check_path: /admin
              health_check_port: 8081
              health_check_protocol: http
              healthy_threshold_count: 3
              port: 8081
              protocol: http
              stickiness_enabled: true
              target_type: instance
              targets:
                - Id: "{{ _ec2_instance_info_dict['molecule-1'].instance_id }}"
                  Port: 8081
                - Id: "{{ _ec2_instance_info_dict['molecule-2'].instance_id }}"
                  Port: 8081
                - Id: "{{ _ec2_instance_info_dict['molecule-3'].instance_id }}"
                  Port: 8081
              unhealthy_threshold_count: 3
              vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"

## License

Copyright (c) Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
