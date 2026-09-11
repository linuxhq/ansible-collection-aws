=========================
linuxhq.aws Release Notes
=========================

.. contents:: Topics

v2.4.3
======

Bugfixes
--------

- ec2_transit_gateway_route_table - wait for deleting static routes to disappear before recreating them.
- ec2_vpc_prefix_list - recognize completed restoration and deletion in waiters.
- eks_cluster - compare only explicitly requested control plane logging states.
- eks_cluster - preserve case-sensitive tag keys in returned cluster data.
- eks_cluster - preserve user tag keys when creating clusters.
- eks_cluster - send related Auto Mode configuration updates in one request.
- glue_connection_info - accept SPARK, ATHENA, or PYTHON strings for the compute environment override.
- iam_oidc_provider - free audience capacity before adding replacements at the 100-audience limit.
- roles - align Molecule regional fixtures and README examples, preserve multi-region test coverage, and use the molecule AWS profile in the profile scenario.
- sqs_queue_info - request a page size so discovery includes queues beyond the first 1000 results.
- ssm_document - preserve arbitrary keys inside script InputPayload objects when comparing, submitting, and returning content.
- ssm_send_command - retry temporarily invisible commands until the configured wait deadline.
- ssm_send_command - wait for invocation results for every reported target before declaring success.

v2.4.2
======

Release Summary
---------------

Preserve existing AWS resources during updates, align shared tag documentation and phone number tag reconciliation, and simplify Molecule configuration and CI triggers.

Minor Changes
-------------

- pinpoint_sms_voice_phone_number - support purge_tags and use phone_number_id with state=present to reconcile tags on an existing number.
- pinpoint_sms_voice_phone_number, pinpoint_sms_voice_phone_pool, route53_resolver, route53_resolver_rule, ssm_association, ssm_document - use the amazon.aws.tags documentation fragment and accept resource_tags as an alias for tags.

Bugfixes
--------

- ec2_vpc_prefix_list - Reject address family changes and report update mismatches without deleting existing prefix lists.
- notifications_contacts - Reject contact name changes without deleting existing contacts or requiring email reactivation.
- route53_resolver - never delete or replace endpoints with state=present; reject immutable changes and report unresolved update mismatches while preserving the endpoint.
- route53_resolver - omit unchanged endpoint type from protocol updates so AWS applies the requested protocols.
- route53_resolver_rule - Reject domain name and rule type changes and report update mismatches without deleting existing rules.

v2.4.1
======

Release Summary
---------------

Maintenance release aligning agent setup guidance, correcting role dependency documentation and metadata, and cleaning up Molecule environment settings.

v2.4.0
======

Release Summary
---------------

Harden AWS module response handling and validation, rewrite EC2 VPN management, and align development tooling and release automation. The EC2 VPN rewrite includes breaking interface and default changes; review the porting notes before upgrading.

Minor Changes
-------------

- acm_certificate_request - add resource_tags as an alias for tags.
- ec2_flow_log - add resource_tags as an alias for tags.
- ec2_transit_gateway_route_table - add C(resource_tags) as an alias for O(tags).
- ec2_vpc_prefix_list - add C(resource_tags) as an alias for O(tags).
- ec2_vpc_vpn - add offline regression tests and Molecule encryption-update coverage; update the VPN role for the new interface.
- ec2_vpc_vpn - apply a single shared tunnel settings entry to both tunnels, discovering their outside IPs internally for updates.
- ec2_vpc_vpn - reconcile encryption, integrity, IKE versions, DH groups, pre-shared keys, tunnel CIDRs, and connection CIDRs on existing VPN connections.
- ec2_vpc_vpn - validate configuration before mutation, compare supplied pre-shared keys safely, and wait for requested routes to become available and route deletions to complete.
- eks_cluster - add C(resource_tags) as an alias for O(tags).
- global_accelerator - add C(resource_tags) as an alias for O(tags).
- iam_oidc_provider - accept ``resource_tags`` as an alias for ``tags``.
- ses_credential - accept C(aws_region) as an alias for the required C(region) option.
- ses_credential - report a missing C(aws_secret_access_key) through Ansible's required-option handling instead of the lookup's validation error.

Breaking Changes / Porting Guide
--------------------------------

- ec2_vpc_vpn - default purge_routes to true; omitted routes, tags, routing mode, and CIDRs are preserved during updates.
- ec2_vpc_vpn - reject CIDRs with host bits set; supply canonical network addresses.
- ec2_vpc_vpn - replace the upstream-derived module with a collection-native implementation; select connections with mutually exclusive name, vpn_connection_id, or native EC2 filters.
- ec2_vpc_vpn - restrict connection_type to ipsec.1, the only supported EC2 VPN connection type.
- ec2_vpc_vpn - use snake_case tunnel options with scalar algorithm and DH group lists; return connection data under vpn_connection and omit customer gateway XML and pre-shared keys.
- ec2_vpc_vpn role - align purge_routes with the module default of true; explicitly supplied route lists replace existing routes unless purge_routes=false.

Bugfixes
--------

- account_region - fail safely when AWS returns a missing or unknown region opt-in status.
- acm_certificate_request - list all ACM certificate key types so existing EC and RSA 3072/4096 certificates can be reused, validate AWS responses, and recheck described certificate status to avoid raw failures, duplicate requests, or returning a certificate that is no longer pending validation or issued.
- ec2_flow_log - fail clearly when EC2 returns matching or newly created flow logs without usable flow log IDs.
- ec2_flow_log_info - fail clearly when EC2 returns a malformed flow log.
- ec2_instance_metadata and ec2_instance_metadata_info - fail clearly instead of treating a malformed EC2 account-level metadata-default response as empty defaults.
- ec2_instance_type_info - fail clearly when EC2 returns malformed instance type information.
- ec2_placement_group_info - fail clearly when EC2 returns malformed placement group information.
- ec2_pricing_info - fail clearly when AWS Pricing returns a malformed price list or product document.
- ec2_serial_console - fail without changing access when EC2 returns a malformed serial console status.
- ec2_serial_console_info - fail clearly when EC2 returns a malformed serial console status.
- ec2_transit_gateway_route_table - fail safely when EC2 returns malformed transit gateway route-table or route data.
- ec2_transit_gateway_route_table_info - fail safely when EC2 returns malformed transit gateway route-table or route data.
- ec2_vpc_prefix_list - fail safely when EC2 returns malformed managed prefix-list or entry data.
- ec2_vpc_prefix_list_info - fail safely when EC2 returns malformed managed prefix-list or entry data.
- ec2_vpc_vpn - fail route waits promptly when the VPN is deleting, deleted, or missing; predict tunnel updates in check mode while pending VPN endpoints are unallocated.
- ec2_vpc_vpn - reject tunnel inside-CIDR updates that collide with another tunnel before modifying the VPN.
- ec2_vpc_vpn - report unmatched ID and filter selectors without suggesting conflicting creation parameters.
- ec2_vpc_vpn - tolerate stale deleted route entries while waiting for recreated routes to become available.
- ec2_vpc_vpn - treat a null StaticRoutesOnly response as dynamic routing, matching an omitted value.
- ec2_vpc_vpn - validate route CIDRs when reconciling or waiting on routes without blocking unrelated VPN deletion or updates.
- ec2_vpc_vpn role - increase default async and polling budgets to one hour for sequential connection and tunnel updates.
- ec2_vpc_vpn role - omit unspecified static_only, routes, and tunnel_options to preserve existing configuration during updates.
- ecs_ecr_info - fail safely when ECR returns malformed repository data.
- eks_cluster - fail safely when EKS returns malformed cluster or update data.
- eks_cluster_info - fail safely when EKS returns malformed cluster list or cluster data.
- global_accelerator - fail safely when Global Accelerator returns malformed accelerator, listener, endpoint group, or tag data.
- global_accelerator_info - fail safely when Global Accelerator returns malformed accelerator, listener, endpoint group, or tag data.
- glue_connection_info - validate AWS responses before transforming connection data.
- iam_account_alias - fail cleanly when AWS returns malformed account alias data.
- iam_account_alias_info - fail cleanly when AWS returns malformed account alias data.
- iam_oidc_provider - add replacement client IDs before removing obsolete IDs.
- iam_oidc_provider and iam_oidc_provider_info - fail cleanly when AWS returns a malformed provider response.
- iam_policy_info - validate IAM entity, inline policy, and policy document responses before returning them.
- notifications_contacts - Preserve existing tags when replacing a contact whose tags were omitted, and validate AWS responses before using required fields.
- notifications_contacts_info - Validate AWS contact and tag responses before returning them.
- notifications_hub - Validate AWS hub responses before making state decisions or returning created resources.
- notifications_hub_info - Validate AWS hub responses before returning them.
- pinpoint_sms_voice_phone_number, pinpoint_sms_voice_phone_number_info, pinpoint_sms_voice_phone_pool, pinpoint_sms_voice_phone_pool_associate, and pinpoint_sms_voice_phone_pool_info - validate AWS responses, avoid waits after resources disappear, prevent stale deletion results, and avoid waiting for existing resources in check mode.
- rds_subnet_group_info - fail cleanly when AWS returns malformed subnet group data.
- route53_delegation_set and route53_delegation_set_info - validate AWS responses and fail cleanly for malformed data.
- route53_resolver - validate endpoint, IP address, tag, and mutation responses and fail clearly instead of raising raw exceptions or reporting unapplied tag changes.
- route53_resolver_info - validate endpoint and paginated detail responses before transforming them.
- route53_resolver_rule - validate rule, target IP, tag, and mutation responses; recover lean create and update responses; reject ambiguous matches; and avoid stale IDs in check-mode replacement results.
- route53_resolver_rule_associate - validate association responses, safely recover lean create responses, reject ambiguous matches, and avoid stale IDs in check-mode replacement results.
- route53_resolver_rule_info - validate rule, association, and tag responses before transforming them and skip association queries when no rules exist.
- route53_zone_associate - validate hosted-zone and VPC-association responses before transforming them.
- service_quota - reject non-finite desired values and validate quota, history, and increase-request responses before using them.
- service_quota_info - validate quota responses and reject mismatched quota and context identifiers.
- ses_identity_info - validate identity names, details, tags, and policies returned by AWS before transforming them.
- ses_identity_tokens_info - validate DKIM and verification token responses while preserving token prepopulation for identities that do not yet exist.
- sns_sms_attributes - fail cleanly when AWS returns malformed SMS attributes.
- sns_topic_attributes - fail cleanly when AWS returns malformed topic attributes.
- sqs_queue_info - fail cleanly when AWS returns malformed queue information.
- ssm_association - fail cleanly when AWS returns malformed association data.
- ssm_association_info - fail cleanly when AWS returns malformed association data, including missing identifiers.
- ssm_document - fail cleanly when AWS returns malformed document data or content.
- ssm_document_info - fail cleanly when AWS returns malformed document data.
- ssm_instance_info - fail cleanly when AWS returns malformed managed instance data. A null instance list or an entry that was not a dictionary previously raised an unhandled traceback.
- ssm_instance_info - warn when a managed instance lacks a valid instance ID, preserve the record in C(instances), and omit the invalid value from C(instance_ids).
- ssm_send_command - clarify that target keys are passed to AWS unchanged and correct the documented example to use the C(InstanceIds) target key, which AWS rejected as C(instanceids).
- ssm_send_command - fail cleanly when AWS returns malformed command or command invocation data instead of raising an unhandled traceback.
- ssm_send_command - fail with a message naming the command ID when AWS returns an invalid command or invocation status value.
- ssm_send_command - reject an empty O(document_name) locally instead of sending an invalid request to AWS.
- ssm_send_command - report C(changed=true) on failures after AWS accepts the command.
- ssm_send_command - return an empty C(command_invocations) list instead of raising an unhandled C(UnboundLocalError) when C(wait=true) and the wait timeout expires before the first poll.
- wafv2_ip_set_info - fail cleanly when AWS returns malformed IP set summary data, and fail instead of returning an empty entry for malformed detail data.
- wafv2_web_acl_info - fail cleanly when AWS returns malformed web ACL summary data, and fail instead of returning an empty entry for malformed detail data.
- wafv2_web_acl_logging - validate AWS SDK response shapes and preserve changed status when post-update validation fails.

Known Issues
------------

- ec2_vpc_vpn - asymmetric tunnel settings may reconfigure both tunnels on the first update after creation because updates use numeric outside-IP order rather than creation list order; this may interrupt connectivity.
- ec2_vpc_vpn - supplying pre_shared_key fails if EC2 withholds the current key because it cannot be compared safely; omit pre_shared_key to preserve it.
- ec2_vpc_vpn role - use the name selector; supplying filters or vpn_connection_id conflicts with the name argument required by the role. Use the module directly when selecting an existing connection by ID or filters.

v2.3.0
======

Minor Changes
-------------

- ec2_vpc_prefix_list - recreate immediately when address_family changes instead of attempting an unsupported modify first.
- ec2_vpc_prefix_list - validate and normalize replacement CIDRs before deleting an existing prefix list.
- ec2_vpc_prefix_list - wait between dependent modifications and replacements, project final no-wait entry updates, and preserve unmanaged tags in additive check mode.
- pinpoint_sms_voice_phone_number - allow all four capabilities accepted by the AWS API.

Bugfixes
--------

- AWS manager modules - fail when mutation responses omit required resource identifiers instead of reporting unusable successful state.
- AWS manager modules - normalize non-string tag keys before validating and sending tags.
- AWS manager modules - normalize tag values and validate service-specific tag counts and key/value lengths before performing mutations.
- AWS manager modules - treat modeled not-found errors during deletion as successful absent-state convergence.
- EC2 info modules - deduplicate flow-log, transit-gateway route-table, placement-group, and managed-prefix-list identifier filters before requests.
- EC2 instance type and ECR repository info modules - deduplicate identifier filters and reject requests above provider limits before calling AWS.
- EC2 transit gateway route tables and Pinpoint SMS Voice pools - validate provider limits after adding managed Name tags.
- EKS cluster and SNS SMS attribute info modules - deduplicate set-like list filters before requests.
- Pinpoint SMS Voice info modules - deduplicate ID filters before provider-limit validation and requests.
- Preserve Resolver endpoint IP details after waiting for an endpoint update.
- Route53 Resolver endpoint and rule modules - treat deletion already in progress as idempotent instead of issuing duplicate delete requests.
- Route53 Resolver manager modules - reject IP address values whose syntax or address family does not match their option.
- Route53 Resolver manager modules - wait for lifecycle prerequisites before recreating or mutating transitioning resources, including when final waiting is disabled.
- Route53 delegation set and WAFv2 info modules - manually follow response markers when Botocore does not provide paginators for list operations.
- Route53 delegation set and WAFv2 info modules - use shared pagination that rejects repeated provider tokens instead of potentially looping forever.
- account_region - wait for an opposite in-progress transition before reversing the requested region state.
- acm_certificate_request - normalize and deduplicate DNS subject alternative names before validation and creation.
- acm_certificate_request - replace certificates that disappear between discovery and detail lookup.
- acm_certificate_request and ssm_association - validate provider list limits before calling AWS, including ACM's 100-name certificate limit.
- ec2_flow_log - preserve successfully created flow-log IDs when the immediate describe response is eventually consistent.
- ec2_flow_log - reject unsupported max_aggregation_interval values before calling AWS.
- ec2_instance_metadata - project updated account defaults instead of returning a stale immediate refresh.
- ec2_pricing_info - reject filter lists above the provider limit before calling AWS.
- ec2_transit_gateway_route_table - allow attachment-backed routes by avoiding a false default that conflicts with the attachment option.
- ec2_transit_gateway_route_table - paginate route searches so route reconciliation covers every matching route.
- ec2_transit_gateway_route_table - validate and normalize every desired route CIDR before applying route changes.
- ec2_transit_gateway_route_table - wait for a deleting route before recreating it, including when final waiting is disabled.
- ec2_transit_gateway_route_table - wait for a pending table before deletion even when final waiting is disabled.
- ec2_transit_gateway_route_table - wait for a pending table before dependent route reconciliation when the final wait is disabled.
- ec2_transit_gateway_route_table_info - paginate route searches instead of failing when more than 1000 routes match.
- ec2_vpc_prefix_list - return the created prefix list directly when wait is disabled instead of immediately querying eventually consistent state.
- ec2_vpc_prefix_list - wait for pre-existing transitions before dependent mutations and avoid repeating an in-progress delete.
- ec2_vpc_prefix_list, global_accelerator, and route53_resolver_rule - validate provider list and port limits before calling AWS.
- ec2_vpc_prefix_list_info - omit prefix lists that disappear while their entries are being gathered.
- eks_cluster - handle deleting clusters as in-flight absence and wait for transition prerequisites before deletion.
- eks_cluster - honor wait_delay when using EKS waiters.
- eks_cluster - ignore duplicate entries when comparing set-like cluster configuration lists.
- eks_cluster - normalize tag values and validate the final tag set before applying multi-step updates.
- eks_cluster - predict no-wait updates without eventually consistent reads and preserve unmanaged tags in additive check mode.
- eks_cluster - reject multiple encryption configurations before calling AWS.
- eks_cluster - wait for a transitioning cluster before applying another requested mutation, including when final waiting is disabled.
- eks_cluster_info - preserve case-sensitive tag keys in returned clusters and tag filters.
- global_accelerator - allow an explicit empty ip_addresses list to clear existing addresses and validate address and listener limits before calling AWS.
- global_accelerator - avoid a Python 3.10-only helper in managed-node module code.
- global_accelerator - fail a missing explicit ARN instead of creating a replacement that the same selector cannot manage.
- global_accelerator - reconcile cross-account endpoint attachment ARN changes and include them in check mode results.
- global_accelerator - reject desired configurations above the fixed 42-endpoint-group accelerator quota before calling AWS.
- global_accelerator - reject duplicate BYOIP addresses before calling AWS.
- global_accelerator - reject overlapping listener ranges and duplicate listener-port overrides before calling AWS.
- global_accelerator - retry listener replacements after freeing a listener when the accelerator is at its listener quota.
- global_accelerator - retry modeled concurrent update conflicts.
- global_accelerator - validate duplicate listeners, endpoint group regions, and endpoints before creating any dependent resources.
- global_accelerator - validate modeled string limits before creating dependent resources.
- global_accelerator - wait for an existing in-progress accelerator before further reconciliation or deletion.
- global_accelerator - wait for parent creation and prerequisite endpoint group and listener removal before dependent operations, even when the final wait is disabled.
- global_accelerator_info - omit accelerators that disappear while their details are being gathered.
- iam_account_alias - replace an existing account alias before creating a new alias.
- iam_account_alias and iam_oidc_provider - retry modeled concurrent IAM mutations during reconciliation.
- iam_oidc_provider - compare hexadecimal certificate thumbprints case-insensitively.
- iam_oidc_provider - compare the case-insensitive issuer host without changing case-sensitive path components.
- iam_oidc_provider - normalize the case-insensitive HTTPS scheme when matching providers by URL.
- iam_oidc_provider - project successful client ID and thumbprint updates instead of returning an eventually consistent refresh.
- iam_oidc_provider - reject non-hexadecimal certificate thumbprints before calling AWS.
- iam_oidc_provider - reject provider creation URLs without the required HTTPS scheme.
- iam_oidc_provider and Pinpoint SMS Voice info modules - validate remaining provider list limits before calling AWS.
- iam_oidc_provider and ssm_document - preserve successful mutation results when immediate eventually consistent reads do not find the resource.
- iam_oidc_provider_info - match provider ARN hostnames case-insensitively when filtering by URL.
- notifications_contacts - retry modeled replacement conflicts while contact deletion propagates.
- notifications_contacts_info - validate required ARN parameter support before calling contact detail and tag APIs.
- notifications_hub - use lifecycle status for idempotence and retry modeled registration conflicts.
- pinpoint_sms_voice_phone_number - match pool and opt-out-list ARN inputs against the IDs and names returned by AWS.
- pinpoint_sms_voice_phone_number - remove pool associations and disable deletion protection before releasing a phone number.
- pinpoint_sms_voice_phone_number - tolerate resources disappearing while removing release prerequisites.
- pinpoint_sms_voice_phone_number_info - report unsupported tag lookup SDKs before querying phone numbers.
- pinpoint_sms_voice_phone_number_info and pinpoint_sms_voice_phone_pool_info - allow ID queries by applying the default owner only after mutually exclusive argument validation.
- pinpoint_sms_voice_phone_pool - avoid redundant create-time tagging, wait before tags that depend on a pool update, and preserve accurate no-wait results.
- pinpoint_sms_voice_phone_pool - disable pool deletion protection before deleting a protected pool.
- pinpoint_sms_voice_phone_pool - do not fabricate an origination identity for existing pools in check mode.
- pinpoint_sms_voice_phone_pool - fail a missing explicit pool ID instead of repeatedly creating pools with different IDs.
- pinpoint_sms_voice_phone_pool - match discovered pools by their managed Name tag when sender identities belong to multiple pools.
- pinpoint_sms_voice_phone_pool - wait for transitioning pools before update or deletion mutations, including when final waiting is disabled.
- pinpoint_sms_voice_phone_pool_associate - allow country-neutral origination identities without an ISO country code.
- pinpoint_sms_voice_phone_pool_info - report unsupported identity and tag lookup SDKs before querying pools.
- plugins - cap custom polling sleeps at their configured timeout deadlines.
- plugins - validate wait bounds on no-wait operations that still require internal dependency waits.
- route53_resolver - interleave endpoint IP replacements to stay within the provider's 2-to-20 address bounds.
- route53_resolver - reject duplicate endpoint IP address definitions before calling AWS.
- route53_resolver - treat provider-assigned addresses as satisfying subnet-only endpoint IP definitions.
- route53_resolver - validate endpoint IP address, protocol, and security group list bounds before calling AWS.
- route53_resolver - validate replacement-sensitive name, subnet, security-group, and tag constraints before deleting an existing endpoint.
- route53_resolver - wait between dependent endpoint IP mutations and predict final IP state when the final wait is disabled.
- route53_resolver and route53_resolver_rule - avoid eventually consistent IP and tag lookups immediately after no-wait creation.
- route53_resolver and route53_resolver_rule - derive create idempotency tokens from desired resource state so replacements do not reuse the original request token.
- route53_resolver and route53_resolver_rule - wait for asynchronous deletion before replacement creation even when final waiting is disabled.
- route53_resolver and ses_sandbox - count and compare set-like inputs after deduplication.
- route53_resolver_rule - avoid unsupported and unnecessary detail and tag lookups when deleting a rule.
- route53_resolver_rule - compare DNS domain names case-insensitively.
- route53_resolver_rule - deduplicate equivalent target IP entries before comparison and requests.
- route53_resolver_rule - reject unsupported rule types and invalid target IP definitions before calling AWS.
- route53_resolver_rule - validate replacement-sensitive name, domain, endpoint, target, and tag constraints before deleting an existing rule.
- route53_resolver_rule - validate wait bounds used by prerequisite waits even when final waiting is disabled.
- route53_resolver_rule_associate - accept overridden rule associations as a terminal state instead of waiting indefinitely.
- route53_resolver_rule_associate - allow associations to be removed without an unused name.
- route53_resolver_rule_associate - avoid disassociating an association again while deletion is already in progress.
- route53_resolver_rule_associate - validate replacement names before deleting an existing association.
- route53_resolver_rule_associate - wait for prerequisite disassociation before replacing a rule association when the final wait is disabled.
- service_quota_info - return an empty result when neither an adjusted nor default quota exists.
- ses_credential - trim surrounding region whitespace before deriving the SMTP password.
- ses_credential - validate that region and secret inputs are non-empty strings.
- ses_identity_tokens_info - fail when SES omits the requested domain tokens.
- ses_sandbox - project successful account detail requests instead of returning an eventually consistent refresh.
- ses_sandbox - reject blank production-access use case and website details before calling AWS.
- sns_topic_attributes - fail check mode when the target topic does not exist instead of predicting an impossible update.
- sqs_queue_info - accept both current JSON and legacy query-protocol missing-queue error codes.
- ssm_association - avoid an eventually consistent tag lookup immediately after creation.
- ssm_association - preserve unmanaged association settings when updating schedule and targets.
- ssm_association - reject empty target values and deduplicate equivalent targets and set-like target values before comparison, validation, and requests.
- ssm_association and ssm_document - retry modeled concurrent Systems Manager mutations.
- ssm_document - preserve the successful update result when the immediate default-version refresh is stale.
- ssm_document - reconcile the default document version through the latest version, as required by Systems Manager.
- ssm_instance_info - deduplicate instance ID filters before provider-limit validation and requests.
- ssm_send_command - do not report a failed command as successful when its returned invocations succeeded.
- ssm_send_command - keep polling until the terminal target count is known and every returned invocation has a terminal status.
- ssm_send_command - keep polling when invocation results lag behind a completed command that reports matched targets.
- ssm_send_command - reject empty targeting and target values, omit empty target requests, and deduplicate equivalent targets, instance IDs, and target values before provider-limit validation and requests.
- ssm_send_command - validate timeout_seconds and all target list bounds before calling AWS.
- wafv2_web_acl_logging - preserve unmanaged redaction and filter settings when changing the logging destination.
- wafv2_web_acl_logging - reject invalid logging destination counts before calling AWS.

v2.2.1
======

Release Summary
---------------

Simplify EKS and Global Accelerator internals and align Global Accelerator validation with external security group management.

v2.2.0
======

Release Summary
---------------

Add Lambda target group and resource policy management.

Minor Changes
-------------

- elb_target_group - Add support for Lambda target groups and target registration.
- lambda_policy - Add a role for managing Lambda resource policy statements.

v2.1.9
======

Release Summary
---------------

This release adds NAT gateway discovery to the ec2_security_group role for inventory-driven traffic hairpinning rules.

Minor Changes
-------------

- ec2_security_group - Add ec2_vpc_nat_gateway_info as a role dependency.

v2.1.8
======

Release Summary
---------------

This release updates the amazon.aws and community.aws dependencies, improves RDS role flexibility and dependency discovery, and makes WAFv2 resource associations resilient to AWS propagation delays.

Minor Changes
-------------

- Update amazon.aws to 11.4.0 and community.aws to 11.1.0.
- rds_instance_param_group - Allow creating parameter groups without params.
- rds_option_group - Add ec2_security_group_info as a role dependency.

Bugfixes
--------

- wafv2_resources - Retry web ACL associations during AWS WAF propagation.

v2.1.7
======

Release Summary
---------------

This release narrows the exception handling in the modules so that only botocore errors are reported as AWS failures, leaving unrelated errors to surface as tracebacks instead of being masked. It also adopts ruff 0.16.0, whose new default rule set replaces the narrow selection the collection had been linting against, drops the now-redundant module shebangs and the ruff per-file-ignores they required, and picks up the latest AWS SDK and toolchain updates.

Minor Changes
-------------

- account_region, acm_certificate_request, ec2_flow_log, ec2_instance_metadata, ec2_placement_group_info, ec2_pricing_info, ec2_serial_console, ec2_serial_console_info, ec2_transit_gateway_route_table, ec2_transit_gateway_route_table_info, ec2_vpc_prefix_list, ec2_vpc_prefix_list_info, ecs_ecr_info, eks_cluster, eks_cluster_info, global_accelerator, global_accelerator_info, glue_connection_info, iam_account_alias, iam_oidc_provider, iam_oidc_provider_info, iam_policy_info, notifications_contacts, notifications_contacts_info, notifications_hub, pinpoint_sms_voice_phone_number, pinpoint_sms_voice_phone_number_info, pinpoint_sms_voice_phone_pool, pinpoint_sms_voice_phone_pool_associate, pinpoint_sms_voice_phone_pool_info, rds_subnet_group_info, route53_delegation_set, route53_delegation_set_info, route53_resolver, route53_resolver_info, route53_resolver_rule, route53_resolver_rule_associate, route53_resolver_rule_info, route53_zone_associate, service_quota, service_quota_info, ses_identity_info, ses_identity_tokens_info, ses_sandbox, sns_sms_attributes, sns_sms_attributes_info, sns_topic_attributes, sqs_queue_info, ssm_association, ssm_association_info, ssm_document, ssm_document_info, ssm_send_command, wafv2_ip_set_info, wafv2_web_acl_info, wafv2_web_acl_logging - catch only C(BotoCoreError) and C(ClientError) around AWS API calls instead of every exception, so unrelated errors surface as tracebacks rather than being reported as AWS failures.

v2.1.6
======

Minor Changes
-------------

- efs - add a role dependency on ec2_security_group_info.
- efs - manage filesystems asynchronously in batches like the other manager roles.
- elb_application_lb - add a role dependency on ec2_security_group_info.
- elb_application_lb - manage load balancers asynchronously in batches like the other manager roles.
- elb_application_lb - the per-item C(wait) key now defaults to V(true) so deletions complete before dependent resources are removed.
- rds_instance - support the per-item C(iam_roles) and C(purge_iam_roles) keys for associating IAM roles with an instance.

Breaking Changes / Porting Guide
--------------------------------

- efs - the role no longer creates security groups; the per-item C(vpc_id), C(rules), and C(rules_egress) keys are removed. Manage groups with the ec2_security_group role and set C(security_groups) on each target instead.
- elb_application_lb - items always require C(name), C(listeners), and C(subnets), including when C(state=absent); append C(state) to the existing item instead of listing only the name.
- elb_application_lb - the role no longer creates security groups; the per-item C(vpc_id), C(rules), and C(rules_egress) keys are removed. Manage groups with the ec2_security_group role and pass C(security_groups) instead.

v2.1.5
======

Release Summary
---------------

This release reworks the rds_instance role to manage instances asynchronously in batches and drops its built-in security group management in favor of the ec2_security_group role, which now creates all groups before populating rules so rules can cross-reference any group managed in the same run. It also prunes unused Python dependencies and picks up the latest AWS SDK and toolchain updates.

Minor Changes
-------------

- ec2_security_group - create all groups before populating rules so rules can reference any group managed in the same run, including groups in later batches.
- ec2_security_group - strip rules from groups being removed before deleting them so cross-referenced groups delete cleanly.
- rds_instance - add a role dependency on ec2_security_group_info.
- rds_instance - manage instances asynchronously in batches like the other manager roles.

Breaking Changes / Porting Guide
--------------------------------

- rds_instance - the role no longer creates security groups; the per-item C(vpc_id), C(rules), and C(rules_egress) keys are removed. Manage groups with the ec2_security_group role and pass C(vpc_security_group_ids) instead.

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
