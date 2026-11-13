# ses\_identity

Manage aws simple email service identities

## Requirements

- botocore 1.42.8 or later, which returns the DKIM signing hosted zone that the DKIM CNAME records point to.

## Role Variables

    ses_identity_list: []

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ses_identity
          ses_identity_list:
            - identity: molecule.org
              zone: molecule.org
            - identity: a.molecule.org
              zone: molecule.org
            - identity: b.molecule.org
              zone: molecule.org
            - identity: c.molecule.org
              zone: molecule.org
