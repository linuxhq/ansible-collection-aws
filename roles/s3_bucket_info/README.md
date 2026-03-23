# s3\_bucket\_info

Gather information about aws simple storage service buckets

## Requirements

None

## Role Variables

    s3_bucket_info_bucket_facts: {}
    s3_bucket_info_name: null
    s3_bucket_info_name_filter: null
    s3_bucket_info_transform_location: false

## Return Values

    _s3_bucket_info_dict
    _s3_bucket_info_list

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.s3_bucket_info
          s3_bucket_info_bucket_facts:
            bucket_accelerate_configuration: true
            bucket_acl: true
            bucket_cors: true
            bucket_encryption: true
            bucket_lifecycle_configuration: true
            bucket_location: true
            bucket_logging: true
            bucket_notification_configuration: true
            bucket_ownership_controls: true
            bucket_policy: true
            bucket_policy_status: true
            bucket_replication: true
            bucket_request_payment: true
            bucket_tagging: true
            bucket_versioning: true
            bucket_website: true
            public_access_block: true
