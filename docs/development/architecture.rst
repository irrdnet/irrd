========================
Architecture / processes
========================

This document described the general architecture of IRRd, and some of the
most important processes that take place in each component.

As a general process note, IRRd performs all major processes in a single
SQL transaction. This includes a single whois query, processing a set of
updates from an NRTM server, processing an email with changes to multiple
objects, or running a fresh import of a mirrored source.
Each of these processes will fail entirely or succeed entirely, which
helps to provide consistency in the database.

Current architecture
--------------------

The basic architecture is this: [#]_

.. image:: ../_static/architecture.svg
 :target: ../_static/architecture.svg

This is intended as an overview, and not every class is included in this
diagram for readability. Significant but out of scope of the diagram are
configuration, which is used, for example, by the authentication checker
to find the override password, but also by the whois server to determine
which port to listen on.

irrd.server.whois
^^^^^^^^^^^^^^^^^
The whois server module deals with whois TCP socket handling and extracting
individual queries. A new thread is started for processing each query.
The parsing is performed by ``WhoisQueryParser``, which then prepares the
right ``RPSLDatabaseQuery`` objects. Each TCP connection maps to a single
``WhoisQueryParser`` instance. Most whois queries map to a single
SQL query, but there are a few exceptions. Some state is also kept in
the query parser, such as whether it's operating in keepalive mode.

irrd.server.http
^^^^^^^^^^^^^^^^
IRRd contains a very simple HTTP server for status info. There is only
a single valid URL, ``/v1/status``. This module contains the HTTP server.

irrd.updates
^^^^^^^^^^^^
This module receives change requests by e-mail or direct submission.
These are first parsed into individual submitted objects, along with their
metadata like PGP signatures. The individual object changes are processed by
`ChangeRequest`. This includes retrieving any existing objects,
to determine whether the change is an add, update or delete. The new object
has its syntax validated, and authentication and referential integrity
checks are performed. Note that for one submission, possibly with multiple
individual changes, a single authentication and reference validator is used,
because their status may on the current validity of other changes in the same
message. The `ChangeSubmissionHandler` resolves these co-dependencies.

The authentication validator will retrieve all relevant mntners for a
particular change, and then attempt to pass an authentication method on
one of them, given the authentication data provided. In addition,
`ChangeSubmissionHandler` provides it with context on which `mntner`
objects may be new in this same submission, which therefore can't be found
in the database and will require special handling.

The reference validator checks that all referenced objects exist, or in case
of deletions, whether there are no more references to the object.
Also here, `ChangeSubmissionHandler` provides context on the current
submission, making it possible to delete two objects that depend on each
other, in one submission. The information on the references between objects
is provided by the RPSL Python objects from `irrd.rpsl`.

Updates to objects may involve a number of notifications, and a single
submission may require notifications to the same or different destinations.
For each authentication check, `AuthValidator` provides all potentially
relevant `mnt-nfy` and `upd-to` attributes on `mntners`, `ChangeRequest`
aggregates the correct one of these two options, depending on validation
status, along with `notify`. This is then aggregated in
`ChangeSubmissionHandler` to ensure no more emails are sent than needed.

All objects submitted to IRRd in this way are processed with
:doc:`strict object validation </admins/object-validation>`.

irrd.storage
^^^^^^^^^^^^
The storage module handles any interaction with the SQL database. It offers
abstractions to perform complex SQL queries, processing
new/updated/deleted objects, and automatic journal keeping. It's documented in
:doc:`more detail in its own documentation </development/storage>`.

irrd.rpsl
^^^^^^^^^
The RPSL module handles RPSL objects along with their syntax, metadata,
validation and extraction of values like primary keys. It is mainly used when
processing imports, NRTM streams and submissions with changes.
The particulars of object validation are
:doc:`documented in more detail </admins/object-validation>`.

The Python representations of RPSL objects in this module also provide
contextual information on the relation between objects. Some, like
`RPSLMntner`, contain additional logic such as validating passwords against
a `mntner` object.

irrd.mirroring
^^^^^^^^^^^^^^
The mirroring module deals with mirroring other databases. This can be done
by periodic full imports, or by an initial import followed by an NRTM stream.

A hook to the Twisted framework regularly calls a scheduler, which in turn
starts the appropriate mirror update runners. Based on the state of the
database and configuration (e.g. is there currently any data? is an NRTM
host configured?) the update is either performed by updates from an NRTM
stream, or by running a full import. A full import can also be forced by
an admin by setting a flag in the database.

Upon each full import, the entire RPSL journal for this mirror is discarded,
as the local copy can no longer be guaranteed to be complete.

See the :doc:`mirroring documentation </users/mirroring>` for more details.
All objects received from mirrors are processed with
:doc:`non-strict object validation </admins/object-validation>`.

irrd.conf
^^^^^^^^^
The configuration module provides other modules access to the IRRd
configuration. It loads a default config, followed by the user's
config file. A SIGHUP will reload the configuration, but only after all
checks have passed on the new config. However, some settings are
only read on startup, and therefore will not take effect until a restart.

The different settings and when they take effect are
:doc:`listed in the configuration documentation </admins/configuration>`.

irrd.scripts
^^^^^^^^^^^^
This module contains scripts intended to be run from the command line.
Most are aimed at development, except ``submit_email``:

* ``submit_email`` will read an email with updates from stdin and process
  them. This is the expected entry point for processing incoming email.
  Note that as a separate script, it **always acts on the current configuration
  file** - not on the configuration that IRRd started with.
* ``submit_changes`` will read direct RPSL submissions from stdin and process
  them. It does not support PGP.
* ``rpsl_read`` reads files with RPSL data, and inserts them into the
  database. It is mainly intended for testing, as it does not include
  aspects like source status metadata updates.
* ``query_qa_comparison`` is used for QA tests in query handling.

irrd.utils
^^^^^^^^^^
The utils module contains a few parts used in other places:

* A class for extracting text and PGP metadata from plain and multipart
  emails, along with other metadata.
* A wrapper around gpg to validate an inline or PGP/MIME signature.
* Sample RPSL objects used for tests.
* Text utilities for working with RPSL paragraphs and lines. Notably,
  when separating RPSL object lines, unicode newline characters must
  not be considered newlines, which is contrary to the behaviour of
  built-in Python functions.
* A small whois client, used by the status info page.

.. [#] This diagram was made with `draw.io`_, and the source file is `part of this repo`_.

.. _draw.io: https://www.draw.io/
.. _part of this repo: _static/architecture.drawio
