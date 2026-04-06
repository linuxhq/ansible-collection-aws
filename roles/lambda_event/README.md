# lambda\_event

Manage aws lambda events

## Requirements

None

## Role Variables

    lambda_event_async: 300
    lambda_event_batch: 10
    lambda_event_delay: 3
    lambda_event_list: []
    lambda_event_poll: 0
    lambda_event_retries: 100

## Return Values

None

## Dependencies

None

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.lambda_event
          lambda_event_list:
            - lambda_function_arn: "arn:aws:lambda:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:function:molecule-pass"
              event_source: sqs
              source_params:
                batch_size: 10
                enabled: true
                source_arn: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-bounce"

            - lambda_function_arn: "arn:aws:lambda:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:function:molecule-pass"
              event_source: sqs
              source_params:
                batch_size: 10
                enabled: true
                source_arn: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-complaint"

            - lambda_function_arn: "arn:aws:lambda:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:function:molecule-pass"
              event_source: sqs
              source_params:
                batch_size: 10
                enabled: true
                source_arn: "arn:aws:sqs:{{ _aws_az_info_list_l.0[:-1] }}:{{ _aws_caller_info_account }}:molecule-delivery"
