# ses\_sandbox

Manage aws simple email service account details

## Requirements

None

## Role Variables

    ses_sandbox_additional_contact_email_addresses: []
    ses_sandbox_contact_language: en
    ses_sandbox_mail_type: transactional
    ses_sandbox_use_case_description: null
    ses_sandbox_website_url: null

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.ses_sandbox
