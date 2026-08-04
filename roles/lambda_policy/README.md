# lambda\_policy

Manage aws lambda policies

## Requirements

None

## Role Variables

    lambda_policy_async: 300
    lambda_policy_batch: 10
    lambda_policy_delay: 3
    lambda_policy_list: []
    lambda_policy_poll: 0
    lambda_policy_retries: 100

## Return Values

None

## Dependencies

* [elb\_target\_group\_info](../elb_target_group_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.lambda_policy
          lambda_policy_list:
            - action: lambda:InvokeFunction
              function_name: molecule-pass
              principal: elasticloadbalancing.amazonaws.com
              source_arn: "{{ _elb_target_group_info_dict['molecule-lambda'].target_group_arn }}"
              statement_id: molecule-elb-target-group
