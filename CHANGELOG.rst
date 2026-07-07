=========================
linuxhq.aws Release Notes
=========================

.. contents:: Topics

v2.1.3
======

Release Summary
---------------

Initial release of global accelerator roles and overall module optimizations

Minor Changes
-------------

- global_accelerator - initial commit
- global_accelerator_info - initial commit

v2.1.2
======

Release Summary
---------------

Add scheme support to elb_application_lb role

v2.1.1
======

Release Summary
---------------

Additional permissions added to splunk_addon role

v2.1.0
======

Release Summary
---------------

Bugfixes and optimizations in custom modules

v2.0.9
======

Release Summary
---------------

Bugfixes and optimizations in custom modules

v2.0.8
======

Release Summary
---------------

Bugfixes and optimizations in custom modules

v2.0.7
======

Release Summary
---------------

Update splunk_addon kms key principals

v2.0.6
======

Release Summary
---------------

Update splunk_addon iam and kms policies

v2.0.5
======

Release Summary
---------------

Addition of splunk_addon role and fixes check_mode in sns_topic_attributes.py if topic doesn't exist

Minor Changes
-------------

- sns_topic_attributes.py - fix check_mode if topic doesn't exist
- splunk_addon - initial commit

v2.0.4
======

Release Summary
---------------

Update standard roles to new standards

v2.0.3
======

Release Summary
---------------

Update standard roles to new standards

v2.0.2
======

Release Summary
---------------

Update ec2 service module to new standards

v2.0.1
======

Release Summary
---------------

Update info roles to new standards

v2.0.0
======

Release Summary
---------------

Initial release that includes a changelog

Minor Changes
-------------

- Add async support to applicable roles
- Add batch operation support to applicable roles
- Add molecule tests to all roles
- Add support for absent state
- Add support for agent workflows
