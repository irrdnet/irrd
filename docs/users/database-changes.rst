=============================
Making changes to IRR objects
=============================

For authoritative databases, changes to objects can be submitted to
IRRd. For each change, a number of integrity, authentication, and reference
checks are performed.
Additionally, notifications may be sent on attempted or successful changes.

.. contents:: :backlinks: none

Submission format & passwords
-----------------------------

.. highlight:: yaml

Changes are submitted by e-mail, to be configured by an IRRd administrator.
Both simple ``text/plain`` e-mails as well as MIME multipart messages with
a ``text/plain`` part are accepted.

The message content should simply be the object texts, separated by an empty
line. If no objects exist with the same primary key, an object creation
is attempted. If an object does exist, an update is attempted.

To delete an object, submit the current version of the object with a
``delete`` attribute in it, without empty lines in between::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    delete: <your deletion reason>

For authentication, ``password`` attributes can be included anywhere
in the submission, on their own or as part of objects, e.g.::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    mnt-by: MNT-EXAMPLE
    password: <password for MNT-EXAMPLE>


You may submit multiple passwords, and each password will be considered
for each authentication check.

For PGP authentication, messages can be signed with a PGP/MIME signature
or inline PGP. PGP signatures and passwords can be combined, and each method
will be considered for each authentication check.

IRRd will attempt to process as many changes as possible, meaning that it's
possible that some changes will fail, and some will succeed. A response will
be sent with the results of the submitted changes, and why any failures
occurred.

All objects submitted are validated for the presence, count and syntax,
though the syntax validation is limited for some attributes.
Values like prefixes are also rewritten into a standard format. If this
results in changes compared to the original submitted text, an info message
is added in the reply.


Override password
-----------------
An override password can be configured, which admins can use
In the same way, admins can use to bypass all authentication requirements.
Even with the override password, changes can only be made to objects in
authoritative databases, and will need to pass checks for syntax and
referential integrity like any other change. Override passwords are provided
in the override attribute, e.g.::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    mnt-by: MNT-EXAMPLE
    override: <override password>

Notifications to maintainers or the address in the ``notify`` attribute are
**not** sent when a **valid** override password was used.

If an invalid override password is used, or if no override password was
configured, the invalid use is logged, and authentication and notification
proceeds as usual, **as if no override password was provided.**

.. note::
    New `mntner` objects can only be created using the override password.


Working with auth hash masking
------------------------------
When querying for a `mntner` object, any lines with password hashes are
masked for security reasons. For example::

    mntner: EXAMPLE-MNT
    auth: CRYPT-PW DummyValue  # Filtered for security
    auth: MD5-PW DummyValue  # Filtered for security
    auth: PGPKEY-12345678

When submitting a new `mntner` object, it must include at least one valid
`auth` value, which can not be a dummy value.

When submitting changes to an existing `mntner` object, there are two options:

* Submit without any dummy values in `auth` values. If otherwise valid, the
  `auth` lines submitted will now be the only valid authentication methods.
* Submit with exclusively dummy values (and optionally, PGP keys) and provide
  a single password in the entire submission. In this case, all password
  authentication hashes are deleted from the object, except for a single
  MD5-PW that matches the password used to authenticate the change.

Any other scenario, like submitting a mix of dummy and real hashes, or
submitting dummy hashes along with multiple ``password`` attributes in
the message, is considered an error.


Referential integrity
---------------------
IRRd enforces referential integrity between objects. This means it is not
permitted to delete an object that is still referenced by other
objects. When an object is created or updated, all references to other
objects, such as a `mntner`, must be valid. This only applies to strong
references, as indicated in the object template. For weak references,
only the syntax is validated.

When creating or deleting multiple objects, these are considered together,
which means that an attempt to delete A and B in one submission, while B depends
on A, the deletion will pass referential integrity checks.
(If authentication fails for the deletion of A, the deletion of B will also
fail, as A still exists.)

In the same way, it's possible to create multiple objects that depend on each
other in the same submission to IRRd.


Authentication checks
---------------------
When changing an object, authentication must pass for one of the
maintainers referred by the affected object itself. In case
of updates to existing objects, this refers to both one of the existing
object maintainers, and one of the maintainers in the newly submitted version.
Using a valid override password overrides the requirement to pass
authentication for the affected objects.

Changes can only be made to authoritative databases.

When creating a new `mntner`, a submission must pass authorisation for
one of the auth methods of the new mntner. Other objects can be submitted
that depend on the new `mntner` in the same submission.


Object templates
----------------

The ``-t`` query can be used to get the object template for a particular
object class. This includes which attributes are permitted, which are
mandatory, look-up keys, primary keys and references to other objects.

For example, at the time of writing the template for a route object,
retrieved with ``-t route``, looks like this::

    route:          [mandatory]  [single]    [primary/look-up key]
    descr:          [optional]   [multiple]  []
    origin:         [mandatory]  [single]    [primary key]
    holes:          [optional]   [multiple]  []
    member-of:      [optional]   [multiple]  [look-up key, weak references route-set]
    inject:         [optional]   [multiple]  []
    aggr-bndry:     [optional]   [single]    []
    aggr-mtd:       [optional]   [single]    []
    export-comps:   [optional]   [single]    []
    components:     [optional]   [single]    []
    admin-c:        [optional]   [multiple]  [look-up key, strong references role/person]
    tech-c:         [optional]   [multiple]  [look-up key, strong references role/person]
    geoidx:         [optional]   [multiple]  []
    roa-uri:        [optional]   [single]    []
    remarks:        [optional]   [multiple]  []
    notify:         [optional]   [multiple]  []
    mnt-by:         [mandatory]  [multiple]  [look-up key, strong references mntner]
    changed:        [mandatory]  [multiple]  []
    source:         [mandatory]  [single]    []

This template shows:

* The primary key is the `route` combined with the `origin`. Only
  one object with the same values for the primary key and source can exist.
  Any change submitted with the same primary key, will be considered an
  attempt to update the current object.
* The `member-of` attribute is a look-up key, meaning it can be used with
  ``-i`` queries.
* The `member-of` attribute references to the `route-set` class. It is a
  weak references, meaning the referred `route-set` does not have to exist,
  but is required to meet the syntax of a `route-set` name. The attribute
  is also optional, so it can be left out entirely.
* The `admin-c` and `tech-c` attributes reference a `role` or `person`.
  This means they may refer to either object class, but must be a
  reference to a valid, existing `person` or `role. This `person` or
  `role` can be created as part of the same submission.


Notifications
-------------
IRRd will always reply to a submission with a report on the requested
changes. Depending on the request and its result, additional notifications
may be sent. The overview below details all notifications that may be
sent.


Authentication and notification overview
----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Type of change
     - Authentication must pass
     - Notifications sent to
   * - Create, auth success
     - New object
     -
       * ``mnt-nfy`` for all maintainers of new object 
       * report sent to the submitter of the change
   * - Create, auth fail
     - New object
     -
       * ``upd-to`` for all maintainers of new object 
       * report sent to the submitter of the change
   * - Update or delete, auth success
     - Existing object and new object
     -
       * ``mnt-nfy`` for all maintainers of existing object 
       * ``notify`` attribute of the existing object
       * report sent to the submitter of the change
   * - Update or delete, auth fail
     - Existing object and new object
     -
       * ``upd-to`` for all maintainers of existing object 
       * report sent to the submitter of the change
   * - Any change, syntax or referential integrity failure
     - ---
     -
       * report sent to the submitter of the change
       * no other notifications sent

"Authentication must pass" means that for each relevant object, at least one
auth method of at least one `mntner` referred by the relevant object
has passed.

**No notifications are sent** if changes are made with a **valid** override
password.
