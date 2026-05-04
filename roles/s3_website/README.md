# s3\_website

Manage aws simple storage service bucket websites

## Requirements

None

## Role Variables

    s3_website_async: 300
    s3_website_batch: 10
    s3_website_delay: 3
    s3_website_list: []
    s3_website_poll: 0
    s3_website_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_website
          s3_website_list: "{{ s3_bucket_list }}"
