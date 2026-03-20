# wafv2\_web\_acl

[![License](https://img.shields.io/badge/license-GPLv3-lightgreen)](https://www.gnu.org/licenses/gpl-3.0.en.html#license-text)

Manage aws wafv2 web acls

## Requirements

None

## Role Variables

    wafv2_web_acl_async: 300
    wafv2_web_acl_batch: 10
    wafv2_web_acl_delay: 3
    wafv2_web_acl_list: []
    wafv2_web_acl_poll: 0
    wafv2_web_acl_retries: 100

## Return Values

None

## Dependencies

None

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

## License

Copyright (c) Linux HeadQuarters

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
