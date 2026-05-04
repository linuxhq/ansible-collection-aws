# ec2\_vpc\_subnet

Manage aws virtual private cloud subnets

## Requirements

None

## Role Variables

    ec2_vpc_subnet_async: 300
    ec2_vpc_subnet_batch: 10
    ec2_vpc_subnet_delay: 3
    ec2_vpc_subnet_list: []
    ec2_vpc_subnet_poll: 0
    ec2_vpc_subnet_retries: 100

## Return Values

None

## Dependencies

* [ec2\_vpc\_net\_info](../ec2_vpc_net_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ec2_vpc_subnet
          ec2_vpc_subnet_list:
            - vpc_id: "{{ _ec2_vpc_net_info_dict['molecule'].id }}"
              subnets:
                - name: molecule-a-00
                  az: us-east-1a
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,0) }}"
                - name: molecule-a-01
                  az: us-east-1a
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,1) }}"
                - name: molecule-a-02
                  az: us-east-1a
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,2) }}"
                - name: molecule-a-03
                  az: us-east-1a
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,3) }}"
                - name: molecule-b-00
                  az: us-east-1b
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,4) }}"
                - name: molecule-b-01
                  az: us-east-1b
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,5) }}"
                - name: molecule-b-02
                  az: us-east-1b
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,6) }}"
                - name: molecule-b-03
                  az: us-east-1b
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,7) }}"
                - name: molecule-c-00
                  az: us-east-1c
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,8) }}"
                - name: molecule-c-01
                  az: us-east-1c
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,9) }}"
                - name: molecule-c-02
                  az: us-east-1c
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,10) }}"
                - name: molecule-c-03
                  az: us-east-1c
                  cidr: "{{ '10.0.0.0/16' | ansible.utils.ipsubnet(24,11) }}"
