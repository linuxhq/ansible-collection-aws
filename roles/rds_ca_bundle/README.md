# rds\_ca\_bundle

Manage aws relational database service certificate authority bundles

## Requirements

None

## Role Variables

    rds_ca_bundle_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.rds_ca_bundle
          rds_ca_bundle_list:
            - url: https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
