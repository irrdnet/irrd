================
RPKI integration
================

IRRd can operate in RPKI-aware mode, where it imports ROA objects and
uses those to suppress `route(6)` objects. IRRd also generates pseudo-IRR
objects that represent ROA data.

.. note::
   This document only contains details specific to the scope filter, and is
   meant to complement the
   :doc:`object suppression overview </admins/object-suppression>`.

.. contents::
   :backlinks: none

Configuring RPKI-aware mode
---------------------------
You can enable RPKI-aware mode by setting ``rpki.roa_source``
to a URL of a ROA export in JSON format. RPKI-aware mode is **enabled**
by default. To disable RPKI-aware mode, set this to ``null``.

As soon as this is enabled and you (re)start IRRd or send a SIGHUP,
IRRd will import the ROAs and mark any invalid existing `route(6)` as
such in the database.

You can exclude sources by setting ``sources.{name}.rpki_excluded``.
Objects from these sources are always seen as ``not_found``.

To disable the RPKI filter, set ``rpki_excluded`` for all sources
to reset the state of all objects to ``not_found``. Once the periodic
import has updated the state of all objects,
unset ``rpki.roa_source`` to disable the RPKI update process.

Pseudo-IRR objects
------------------
IRRd creates a pseudo-IRR object for each ROA. These can be queried like
any other IRR object, and are included in the output of queries like
``!g``. Their source is set to ``RPKI``, and therefore it is invalid
to add a regular IRR source with that name, when RPKI-aware mode
is enabled. The ``RPKI`` source can be enabled or disabled like any
other source with ``!s`` and ``-s``, and can be included in the
``sources_default`` setting to be included in responses by default.

Validation
----------
IRRd uses `RFC6811 origin validation <https://tools.ietf.org/html/rfc6811>`_.
Objects that are RPKI invalid are suppressed.

Query responses
---------------
In addition to filtering suppressed objects from queries,
query responses for the text of `route(6)` objects include a
``rpki-ov-state`` attribute, showing the current status.
This attribute is discarded from any objects submitted to IRRd,
and omitted for pseudo-IRR objects.

.. _rpki-notifications:

Notifications
-------------
If a route(6) object in an authoritative source is newly marked RPKI invalid,
a notification may be sent to all contacts. Contacts are determined as any email
address, of any tech-c and admin-c, on any mnt-by on the route object,
combined with any mnt-nfy of any of those maintainers.
Emails are aggregated, so a single address will receive a single email with
all objects listed for which it is a contact.

This behaviour is enabled or disabled with the ``rpki.notify_invalid_enabled``
setting. If you have any authoritative sources configured, you must explicitly
set this to ``true`` or ``false`` in your configuration.

"Newly" invalid means that an object was previously valid or not_found, but
a ROA update has changed the status to invalid. At the time this happens,
the email is sent. If the status returns to valid or not_found, no email
is sent. If it then returns to invalid, a new email is sent.

When first enabling RPKI-aware mode, a large number of objects may be marked
as newly invalid, which can cause a large amount of notifications.

Notifications are never sent for objects from non-authoritative sources.

.. danger::
    Care is required with the ``rpki.notify_invalid_enabled`` setting in testing
    setups with live data, as it may send bulk emails to real resource contacts,
    unless ``email.recipient_override`` is also set.

First import with RPKI-aware mode
---------------------------------
Along with the concerns mentioned in
:doc:`object suppression </admins/object-suppression>`, depending on
``rpki.notify_invalid_enabled``, many emails may be sent out
as well.

Temporary inconsistencies
-------------------------
In addition to the cases documented in the
:doc:`object suppression </admins/object-suppression>` documentation,
there are two situations that can cause temporary RPKI inconsistencies.

First, when someone adds a ROA and a `route` object in a mirrored source,
the ROA may not be imported by the time the `route` object is received
over NRTM. The object may initially be marked as RPKI not_found, or, depending
on the ROA change, as invalid. This will be resolved at the next ROA import.

Second, when someone attempts to create a `route` object in an authoritative
source and has just created or modified a ROA, the ROA may not have been
imported yet. This can cause the object to be initially marked as RPKI
not_found, or if the `route` is RPKI invalid without the ROA change,
rejected for being invalid. This will be resolved at the next ROA import,
allowing the user to create the `route`.
When a user attempts to create any `route` that is RPKI invalid, the error
messages includes a note of the configured ROA import time.

.. _rpki-slurm:

SLURM support
-------------
IRRd supports `RFC8416`_ SLURM files to filter or amend the ROAs imported
from ``rpki.roa_source``.
The path to the SLURM file is set in ``rpki.slurm_source``. This supports
HTTP(s), FTP or local file URLs, in ``file://<path>`` format.

The ``prefixAssertions`` entries in the SLURM file are processed as if they
were ROAs from ``rpki.roa_source``. This includes being used in RPKI
validation and creating pseudo-IRR objects. Their trust anchor is set to
"SLURM".

The ``prefixFilters`` entries are used to filter the ROAs from
``rpki.roa_source``. ROAs that match a filter are discarded. They are not
considered in RPKI validation, and no pseudo-IRR objects are created.

The ``bgpsecFilters`` and ``bgpsecAssertions`` entries are ignored.

.. _RFC8416: https://tools.ietf.org/html/rfc8416
