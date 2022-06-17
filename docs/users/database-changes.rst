=============================
Making changes to IRR objects
=============================

For authoritative databases, you can submit changes to objects to
IRRd. For each change, a number of integrity, authentication, and reference
checks are performed.
Additionally, notifications may be sent on attempted or successful changes.

.. highlight:: yaml

Submission format
-----------------
There are two ways to submit changes directly to IRRd:

* By sending an e-mail with the RPSL objects. This method supports BCRYPT-PW,
  MD5-PW, CRYPT-PW and PGPKEY authentication. You will receive a reply by
  e-mail with the result.
* Over HTTPS, through a REST API. This method supports BCRYPT-PW, MD5-PW and
  CRYPT-PW authentication. You receive the results in the HTTP response.

All objects submitted are validated for the presence, count and syntax,
though the syntax validation is limited for some attributes.
Values like prefixes are also rewritten into a standard format. If this
results in changes compared to the original submitted text, an info message
is added in the response.

IRRd will attempt to process as many changes as possible, meaning that it's
possible that some changes will fail, and some will succeed. A response will
be sent with the results of the submitted changes, and why any failures
occurred.

Submitting over HTTP
^^^^^^^^^^^^^^^^^^^^
To submit changes over HTTP, make a POST or DELETE request to ``/v1/submit/``.
For example, if the IRRd instance is running on ``rr.example.net``, the URL is::

    https://rr.example.net/v1/submit/

The expected request body is a JSON object, with a number of keys:

* ``objects``: a list of objects. Each is a JSON object with
  either a ``object_text`` key containing the full RPSL text,
  or an ``attributes`` key which is a list of objects, each having a
  ``name`` and ``value`` key.
  In other words, you can choose to submit the full object text, or
  the individual attributes separately. The ``value`` key may also be
  a list, which will be translated into RPSL by IRRd.
* ``passwords``: an optional list of passwords to use for authentication.
  Each password will be considered for each object to be changed.
* ``delete_reason``: an optional string with the reason for object deletion.
* ``override``: an optional string containing the override password.

If your request is an HTTP POST, the objects are created or modified, depending
on whether an object already exists with the same primary key and source.
If your request is an HTTP DELETE, the objects are deleted.

This is an example of a body that creates/modifies two objects.
One uses the ``object_text`` option to provide a single string,
the other specifies individual attributes::

    {
        'objects': [
            {
                'object_text': 'person: PERSON1-TEST\n...'
            },
            {
                'attributes': [
                    {
                        'name': 'person',
                        'value': 'PERSON2-TEST'
                    },
                    {
                        'name': 'mnt-by',
                        'value': ['DEMO-TEST', 'DEMO2-TEST']
                    }
                ]
            }
        ],
        'passwords': ['password1', 'password2']
    }

.. _database-changes-http-api-response:

There are two possible responses:

* If there is a syntax error in your JSON object, you will receive
  a ``text/plain`` response with status code 400. The response will
  tell you what the issue is with your JSON.
* If the request was syntactically valid, you always receive a
  ``text/json`` response with status code 200, and the details of
  your change.

Here is an example of a JSON response::

    {
        "request_meta": {
            "HTTP-client-IP": "127.0.0.1",
            "HTTP-User-Agent": "user-agent"
        },
        "summary": {
            "objects_found": 2,
            "successful": 1,
            "successful_create": 0,
            "successful_modify": 1,
            "successful_delete": 0,
            "failed": 1,
            "failed_create": 1,
            "failed_modify": 0,
            "failed_delete": 0
        },
        "objects": [
            {
                "successful": true,
                "type": "modify",
                "object_class": "mntner",
                "rpsl_pk": "TEST-MNT",
                "info_messages": [],
                "error_messages": [],
                "new_object_text": "[trimmed]",
                "submitted_object_text": "[trimmed]"
            },
            {
                "successful": false,
                "type": "create",
                "object_class": "person",
                "rpsl_pk": "PERSON-TEST",
                "info_messages": [],
                "error_messages": [
                    "Mandatory attribute \"address\" on object person is missing"
                ],
                "new_object_text": None,
                "submitted_object_text": "[trimmed]"
            }
        ]
    }

The order of the ``objects`` in the response matches the order
of ``objects`` in your request.

Submitting over e-mail
^^^^^^^^^^^^^^^^^^^^^^
The e-mail destination is configured by the IRRd administrator.
Both ``text/plain`` e-mails as well as MIME multipart messages with
a ``text/plain`` part are accepted.

The message content should be the object texts, each separated by an empty
line. If no objects exist with the same primary key, an object creation
is attempted. If an object does exist, an update is attempted.

To delete an object, submit the current version of the object with a
``delete`` attribute in it, without empty lines in between::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    delete: <your deletion reason>

For authentication, you can include ``password`` attributes anywhere
in the submission, on their own or as part of objects, e.g.::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    mnt-by: MNT-EXAMPLE
    password: <password for MNT-EXAMPLE>


You may submit multiple passwords, and each password will be considered
for each authentication check.

For PGP authentication, sign your message with a PGP/MIME signature
or inline PGP. You can combine PGP signatures and passwords, and each method
will be considered for each authentication check.

.. _database-changes-irr-rpsl-submit:

Submission through irr_rpsl_submit
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can also use the ``irr_rpsl_submit`` command to submit changes to IRRd.
It is similar to the submit tool from IRRD v3, but calls the HTTP API under
the hood. So unlike IRRD v3's version, it does not perform any validation
itself - it is mostly a wrapper around the HTTP API.

The main purpose of this script is to provide (limited) compatibility
with existing integrations that called irr_rpsl_submit directly to submit
to older IRRd versions. The IRRD v4 version does need different arguments.

The command reads database objects from stdin in the same format as used
in emails and prints a report to stdout.
You must provide a URL to the IRRd HTTP API, and may enable
debug logging or pass extra metadata.

.. warning::
   The input should not include any email headers. It is not recommended
   to use this script to handle incoming email changes - see the
   `deployment guide </admins/deployment>`_ for the ``irrd_submit_email``
   instead.

This command is included in the IRRd distribution, but is also
`usable as a separate Python script for Python 3.7 or newer <../../_static/irr_rpsl_submit.py>`_.
This script does not have
any dependencies on IRRd or other Python libraries to make deployment
on other hosts easier. You do not need a virtualenv, IRRd config file or
SQL database on hosts that only run ``irr_rpsl_submit``. You can run this
script on its own with any supported Python interpreter.


Override password
-----------------
An IRRd administrator can configure an override password.
This bypasses all authentication requirements.
Even with the override password, changes can only be made to objects in
authoritative databases, and will need to pass checks for syntax and
referential integrity like any other change.

In HTTP submission, provide the override password in the root object, e.g.::

    {
        'objects': [....],
        'override': '<override password>'
    }

In e-mails, provide the password in the override pseudo-attribute, e.g.::

    route: 192.0.2.0/24
    origin: AS65536
    [other object data]
    mnt-by: MNT-EXAMPLE
    override: <override password>

Like the password pseudo-attribute, this can occur at any place in the e-mail.

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
    auth: BCRYPT-PW DummyValue  # Filtered for security
    auth: MD5-PW DummyValue  # Filtered for security
    auth: PGPKEY-12345678

When you submit a new `mntner` object, it must include at least one valid
`auth` value, which can not be a dummy value.

When you submit changes to an existing `mntner` object, there are two options:

* Submit without any dummy values in `auth` values. If otherwise valid, the
  `auth` lines submitted will now be the only valid authentication methods.
* Submit with exclusively dummy values (and optionally, PGP keys) and provide
  a single password in the entire submission. In this case, all password
  authentication hashes are deleted from the object, except for a single
  BCRYPT-PW that matches the password used to authenticate the change.

Any other scenario, like submitting a mix of dummy and real hashes, or
submitting dummy hashes along with multiple ``password`` attributes in
the message, is considered an error.


Referential integrity
---------------------
IRRd enforces referential integrity between objects. This means you are not
permitted to delete an object that is still referenced by other
objects. When you create or update an object, all references to other
objects, such as a `mntner`, must be valid. This only applies to strong
references, as indicated in the object template. For weak references,
only the syntax is validated.

When you create or delete multiple objects in one request, these are evaluated
together, which means that if you attempt to delete A and B in one submission,
while B depends on A, the deletion will pass referential integrity checks.
(If authentication fails for the deletion of A, the deletion of B will also
fail, as A still exists.)

In the same way, you can create multiple objects that depend on each
other in the same submission to IRRd.


Authentication checks
---------------------
When you change an object, authentication must pass for one of the
maintainers referred by the affected object itself. In case
of updates to existing objects, this refers to both one of the existing
object maintainers, and one of the maintainers in the newly submitted version.
Using a valid override password overrides the requirement to pass
authentication for the affected objects.

You can only make changes to objects in authoritative databases.

When you create a new `mntner`, a submission must pass authorisation for
one of the auth methods of the new mntner. You can submit other objects
that depend on the new `mntner` in the same submission.

.. _auth-related-mntners-route:

Related maintainers in route objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When you create new `route(6)` objects, authentication also needs to pass
for the parent object. IRRd searches for the parent object in the following
order, only considering the first match, only looking in the same IRR source:

* An `inet(6)num` that is an exact match to the new `route(6)`.
* The smallest `inet(6)num` that is a less specific of the new `route(6)`.
* The smallest `route(6)` that is a less specific of the new `route(6)`.

If no objects match, there is no parent object, and there are no extra
authentication requirements.
This behaviour can be disabled by setting
``auth.authenticate_parents_route_creation`` to false.
These requirements do not apply when you change or delete existing objects.

.. _auth-related-mntners-set:

Related maintainers in set objects
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When you create new set objects, you may need to pass authentication for the
parent `aut-num` object.
RPSL set objects are `as-set`, `filter-set`, `peering-set`, `route-set` and
`rtr-set`.

The details of this behaviour and the strictness of the checks are
:ref:`configured by the IRR operator <conf-auth-set-creation>`. This may
include a requirement to:

* Include an ASN prefix in the name of your set, e.g. ``AS65537:AS-EXAMPLE``
  being valid, but ``AS-EXAMPLE`` being invalid.
* Pass authentication for the corresponding `aut-num`, e.g. AS65537 in the
  example, skipping this check if the `aut-num` does not exist.
* Pass authentication for the corresponding `aut-num`, e.g. AS65537 in the
  example, failing this check if the `aut-num` does not exist.

These requirements do not apply when you change or delete existing objects.
When looking for corresponding `aut-num` objects,
IRRd only looks in the same IRR source.

Object templates
----------------

You can use the ``-t`` query to get the object template for a particular
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
    changed:        [optional]   [multiple]  []
    source:         [mandatory]  [single]    []

This template shows:

* The primary key is the `route` combined with the `origin`. Only
  one object with the same values for the primary key and source can exist.
  Any change submitted with the same primary key, will be considered an
  attempt to update the current object.
* The `member-of` attribute is a look-up key, meaning it can be used with
  ``-i`` queries.
* The `member-of` attribute references to the `route-set` class. It is a
  weak reference, meaning the referred `route-set` does not have to exist,
  but is required to meet the syntax of a `route-set` name. The attribute
  is also optional, so it can be left out entirely.
* The `admin-c` and `tech-c` attributes reference a `role` or `person`.
  This means they may refer to either object class, but must be a
  reference to a valid, existing `person` or `role`. This `person` or
  `role` can be created as part of the same submission.


Notifications
-------------
IRRd will always reply to a submission with a report on the requested
changes. Depending on the request and its result, additional notifications
may be sent. The overview below details all notifications that may be
sent.

IRRd collects some metadata for each request, which is included in
notifications to maintainers and written to the server logs. For emails,
this includes the from, date, subject and message ID headers
For HTTP requests (including ``irr_rpsl_submit``) this includes the source IP,
user agent and x-irrd-metadata header content.


Authentication and notification overview
----------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Type of change
     - Authentication must pass
     - Notifications sent to
   * - Create, auth success
     - New object and parent object, if any
     -
       * ``mnt-nfy`` for all maintainers of new object 
       * report sent to the submitter of the change
   * - Create, auth fail not through parent object
     - New object and parent object, if any
     -
       * ``upd-to`` for all maintainers of new object 
       * report sent to the submitter of the change
   * - Create, auth fail through parent object
     - New object and parent object
     -
       * ``upd-to`` for all maintainers of parent object
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
