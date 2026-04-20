# ssm\_proxy

Configure local session manager proxy to backend aws service

## Requirements

* [awscli](https://pypi.org/project/awscli)
* [session-manager-plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)

## Role Variables

    ssm_proxy_host: null
    ssm_proxy_instance: null
    ssm_proxy_port: null

## Return Values

None

## Dependencies

* [eks\_cluster\_info](../eks_cluster_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ssm_proxy
          ssm_proxy_host: localhost
          ssm_proxy_instance: molecule
          ssm_proxy_port: 22
