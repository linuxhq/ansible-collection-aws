# wafv2\_web\_acl

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws wafv2 web acls

## Requirements

None

## Role Variables

    wafv2_web_acl_list: []

## Return Values

None

## Dependencies

* [wafv2\_ip\_set\_info](../wafv2_ip_set_info)

## Example Playbook

    - hosts: aws
      connection: local
      roles:
        - role: linuxhq.aws.wafv2_web_acl
          wafv2_web_acl_list:
            - name: molecule
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesAmazonIpReputationList
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesAmazonIpReputationList
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesAmazonIpReputationList
                    sampled_requests_enabled: true

            - name: molecule-commonruleset
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesCommonRuleSet
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesCommonRuleSet
                      excluded_rules:
                        - Name: GenericRFI_BODY
                        - Name: SizeRestrictions_BODY
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesCommonRuleSet
                    sampled_requests_enabled: true

            - name: molecule-knownbadinputsruleset
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesKnownBadInputsRuleSet
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesKnownBadInputsRuleSet
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesKnownBadInputsRuleSet
                    sampled_requests_enabled: true

            - name: molecule-linuxruleset
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesLinuxRuleSet
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesLinuxRuleSet
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesLinuxRuleSet
                    sampled_requests_enabled: true

            - name: molecule-anonymousiplist
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesAnonymousIpList
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesAnonymousIpList
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesAnonymousIpList
                    sampled_requests_enabled: true

            - name: molecule-sqliruleset
              scope: regional
              default_action: Allow
              rules:
                - name: AWS-AWSManagedRulesSQLiRuleSet
                  priority: 0
                  override_action:
                    none: {}
                  statement:
                    managed_rule_group_statement:
                      name: AWSManagedRulesSQLiRuleSet
                      vendor_name: AWS
                  visibility_config:
                    cloud_watch_metrics_enabled: true
                    metric_name: AWS-AWSManagedRulesSQLiRuleSet
                    sampled_requests_enabled: true
