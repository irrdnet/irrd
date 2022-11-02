============
Event Stream
============

.. danger::
    This is early documentation on a feature in development.
    Details and particularly all naming is subject to finetuning.

IRRd can provide an WebSocket event stream of push messages for all changes
to IRR objects. In the future, this may contain other events in IRRd.
There is also an HTTP request to retrieve an initial copy of the IRR data
for clients who want to maintain their own state.

This may seem similar to :doc:`mirroring </users/mirroring>`, but there
are several major differences:

* Mirroring is completely separated by IRR source, the event stream is one
  stream per IRRd instance.
* Mirroring is intended for large numbers of clients, the event stream
  does not scale as well.
* The mirroring protocols are complex to implement, and are typically only
  used between IRRd instances. The event stream uses WebSocket, JSON and
  JSONL, making it easier to use it in custom code.

Retrieval of all initial data is required for any clients that want to
maintain their own local state of the IRR database. This is not needed
for clients that are only interested in following changes.


Initial retrieval over HTTPS
----------------------------
To retrieve all current IRR data, make a GET request to ``/event-stream/``
on the IRRd instance. There are two optional GET parameters to filter the
returned data:

* ``sources``: a comma-separated list of source names
* ``object_classes``: a comma-separated list of RPSL object classes

Without parameters, all objects are returned.

The return format is JSONL.
The first line contains metadata about the response, e.g.::

    {
        "data_type": "irrd_event_stream_initial_download",
        "sources_filter": [
            "EXAMPLE"
        ],
        "object_classes_filter": [
            "route6"
        ],
        "max_serial_journal": 424242,
        "last_change_timestamp": "2022-11-02T13:26:17.777893+00:00",
        "generated_at": "2022-11-02T13:29:50.008351",
        "generated_on": "host.example.net"
    }

The fields are:

* ``data_type``: a fixed key to indicate the data type.
* ``sources_filter`` and ``object_classes_filter``: the filters as set in
  the GET parameters of the request.
* ``max_serial_journal``: the journal serial number of the most recent
  change that was included in this data. Note that this is not an NRTM
  serial - this serial is global for the entire journal of this IRRd instance.
* ``last_change_timestamp``: the timestamp of the most recent change
  that was included in this data.
* ``generated_at`` and ``generated_on``: the timestamp at which the data
  was generated and the hostname of the generator.

The next lines contain IRR objects, e.g.::

    {
        "pk": "2001:db8::\/48AS65530",
        "object_class": "route6",
        "object_text": "route6: ...\norigin: ...\n",
        "source": "RIPE",
        "updated": "2022-05-24 22:18:22.085485+00"
    }

Note that the request may take up to 10
minutes, depending on the size of your database, and that it may take
a few minutes for data to start streaming.

.. danger::
    This endpoint is not designed for frequent requests at this time.


WebSocket stream for changes
----------------------------

The WebSocket stream is available on ``/event-stream/`` and works as follows:

* The server sends a ``stream_status`` message with info on the status
  of the local database.
* The client sends a subscribe message.
* The server streams messages of type ``rpsl_journal`` or ``event_rpsl``.

Stream status
^^^^^^^^^^^^^
The ``stream_status`` message includes these keys:

* ``streamed_sources``: a list of sources for which this instance can
  provide streaming data.
* ``last_reload_times``: the timestamp per source of the last full reload.
  See the section below for the relevance of this.

Example::

    {
        "message_type": "stream_status",
        "streamed_sources": ["EXAMPLE"],
        "last_reload_times": {
            "EXAMPLE": "2022-05-24T18:54:15.569301+00:00"
        }
    }

Subscription
^^^^^^^^^^^^
To receive updates, the client must send a ``subscribe`` message, with
``event_type`` set to ``rpsl`` and ``after_journal_serial`` set to the
journal-wide serial that the stream should start after.

Example::

    {
        "message_type": "subscribe",
        "event_type": "rpsl",
        "after_journal_serial": 424242
    }

The ``after_journal_serial`` value would typically be the
``max_serial_journal`` value from an initial file
or the ``serial_journal`` value from the most recently processed
RPSL journal message.

IRRd does not reply to a valid subscription message.

RPSL journal
^^^^^^^^^^^^
The ``rpsl_journal`` message contains an update to the RPSL journal.
The message contains a key ``event_data`` which in turn contains:

* ``operation``: the type of change, either ``add_or_update`` or ``delete``.
* ``origin``: the reason for the update. Can include ``mirror`` for NRTM,
  ``auth_change`` for authoritative submissions, ``rpki_status`` for a change
  in RPKI validity.
* ``timestamp``: the timestamp of the change.
* ``serial_journal``: the journal-wide serial of this change, i.e. the same
  type of serial referred by ``max_serial_journal`` in initial files
  and ``after_journal_serial`` in subscribe messages.
* ``serial_nrtm``: the NRTM serial of this change, in the context of a single
  IRR source.
* ``pk``, ``object_class``, ``object_text``, ``source``: the RPSL primary key,
  object class full text and IRR source of the object. For ``add_or_update``,
  this is always the new version of the object.

Event RPSL
^^^^^^^^^^
The ``event_rpsl`` message contains other push events in IRRd.
The message contains a key ``event_data`` which in turn contains:

* ``source``: the IRR source to which this event applies.
* ``operation``: the operation, either ``journal_extended`` or ``full_reload``.
  When the journal is extended, this is followed by RPSL journal messages.
  For full reload, see below.

.. note:
    The ``journal_extended`` messages are currently still somewhat
    erratic.


Full reloads
------------
The event stream is based on the internal IRRd journal. This journal
includes all changes to IRR objects, when enabled, and therefore,
taking an initial file and following updates will correctly reflect
the current state of the database.

However, this is not the case in "full reloads": when all records
for a source are deleted from an IRRd instance, and a fresh reload
is done. Operators typically due this for sources they are mirroring,
when their mirror has run out of sync too far.

If such a reload happens while you are following the event stream,
you may miss changes to the database. To recover, you must delete
your local data for this source, load the initial data, and then
resume following the stream from that point.

There are two ways for you to notice that this has happened:

* The ``last_reload_times`` for a source in the ``stream_status``
  message is more recent than your last full import from an
  initial file.
* You receive a ``event_rpsl`` message where the ``operation``
  is ``full_reload``.


Filtering
---------
Password hashes from `mntner` objects are removed in all output.

When a server is in :doc:`RPKI-aware mode </admins/rpki>` or has
the :doc:`scopefilter </admins/scopefilter>` enabled, IRR objects
that are out of scope or RPKI invalid are omitted in the initial
retrieval. Objects that become RPKI invalid or out of scope
are included in the websocket stream as a deletion, with the
``origin`` indicating this reason.
