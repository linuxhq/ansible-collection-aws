# lambda

Manage aws lambda functions

## Requirements

None

## Role Variables

    lambda_async: 300
    lambda_batch: 10
    lambda_delay: 3
    lambda_list: []
    lambda_poll: 0
    lambda_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.lambda
          lambda_list:
            - name: molecule-pass
              architecture: x86_64
              environment_variables:
                MOLECULE: 'true'
              handler: lambda_function.lambda_handler
              memory_size: 128
              role: "arn:aws:iam::{{ _aws_caller_info_account }}:role/molecule-pass"
              runtime: python3.11
              tracing_mode: PassThrough
              zip_file: "{{ role_path | d }}/files/pass.zip"
