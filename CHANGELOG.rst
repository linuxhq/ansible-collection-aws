=========================
linuxhq.aws Release Notes
=========================

.. contents:: Topics

v2.1.4
======

Release Summary
---------------

Shared module_utils helpers, botocore support gating across all modules, and a region override for the s3_bucket role.

Minor Changes
-------------

- ec2_flow_log_info, ec2_instance_type_info, ec2_placement_group_info, ec2_pricing_info, ec2_serial_console_info, ec2_transit_gateway_route_table_info, ec2_vpc_prefix_list_info, ecs_ecr_info, eks_cluster_info, glue_connection_info, iam_account_alias_info, iam_policy_info, rds_subnet_group_info, route53_delegation_set_info, route53_resolver_rule_info, ses_identity_info, ses_identity_tokens_info, ses_sandbox_info, sns_sms_attributes_info, sqs_queue_info, ssm_association_info, ssm_document_info, ssm_instance_info, wafv2_ip_set_info, wafv2_web_acl_info - verify the required botocore client methods and parameters are available and fail with a clear message when the installed botocore is too old.
- modules - refactor shared logic into module_utils helpers for SDK gating, paginated queries, waiters, and tag reconciliation.
- notifications_hub, route53_zone_associate - rely on AWS to validate region names instead of a client-side pattern.
- s3_bucket - support a per-bucket region override in the role.

v2.1.3
======

Release Summary
---------------

Initial release of the global accelerator modules and roles, plus an optimization pass across all modules.

Minor Changes
-------------

- global_accelerator - initial commit of the manager and info roles.
- modules - optimization pass across all modules.

New Modules
-----------

- global_accelerator - Manage aws global accelerators
- global_accelerator_info - Gather information about aws global accelerators

v2.1.2
======

Release Summary
---------------

Add scheme support to the elb_application_lb role.

Minor Changes
-------------

- elb_application_lb - add scheme support to the role.

v2.1.1
======

Release Summary
---------------

Additional permissions added to the splunk_addon role.

Minor Changes
-------------

- splunk_addon - add additional permissions to the role.

v2.1.0
======

Release Summary
---------------

Bugfix for wafv2_web_acl_info result serialization.

Bugfixes
--------

- wafv2_web_acl_info - normalize bytes and timestamp values in returned web ACLs so results serialize cleanly.

v2.0.9
======

Release Summary
---------------

Module optimization pass.

Minor Changes
-------------

- modules - optimization pass across the ec2, eks, pinpoint, route53, ses, sns, and wafv2 modules.

v2.0.8
======

Release Summary
---------------

License header cleanup across every plugin and molecule tagging coverage for the roles.

Minor Changes
-------------

- plugins - update the license header on every module and lookup plugin.
- roles - extend molecule scenarios with tagging tests.

v2.0.7
======

Release Summary
---------------

Update splunk_addon kms key principals.

Minor Changes
-------------

- splunk_addon - update the KMS key principals.

v2.0.6
======

Release Summary
---------------

Update splunk_addon iam and kms policies.

Minor Changes
-------------

- splunk_addon - update the IAM and KMS policies.

v2.0.5
======

Release Summary
---------------

Addition of the splunk_addon role and a check mode fix in sns_topic_attributes.

Minor Changes
-------------

- roles - sort defaults alphabetically and sync README sections.
- splunk_addon - initial commit.

Bugfixes
--------

- sns_topic_attributes - fix check mode when the topic does not exist.

v2.0.4
======

Release Summary
---------------

Follow-up standardization pass across the manager modules.

Minor Changes
-------------

- modules - follow-up standardization pass across the manager modules.

v2.0.3
======

Release Summary
---------------

Bring the remaining manager modules up to the collection standards.

Minor Changes
-------------

- modules - align the eks, iam, notifications, pinpoint, route53, service quota, ses, sns, ssm, and wafv2 managers with the collection authoring standards, including botocore method checks.

v2.0.2
======

Release Summary
---------------

Bring the account, acm, and ec2 manager modules up to the collection standards.

Minor Changes
-------------

- modules - align the account_region, acm_certificate_request, and ec2 manager modules with the collection authoring standards.

v2.0.1
======

Release Summary
---------------

Standardization pass across the info modules and info roles.

Minor Changes
-------------

- modules - align twenty-eight info modules with the collection authoring standards.
- roles - align twelve info roles with the role authoring standards.

v2.0.0
======

Release Summary
---------------

Initial release that includes a changelog.

Minor Changes
-------------

- collection - add agent workflow rules for module and role authoring.
- roles - add absent state support to the manager roles.
- roles - add async support to applicable roles.
- roles - add batch operation support to applicable roles.
- roles - add molecule scenarios to all roles.
