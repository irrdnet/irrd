============
Architecture
============

.. caution::
   At this time, this is a rough plan for the IRRDv4 architecture, and this
   will evolve as the project progresses and new insights are gained.

Goals
-----

The design is intended to support both existing interfaces and allow
integration of new ones. For example, text query formats are decoupled
from the actual processing of queries. Similarly, the definition of RPSL
attributes on objects are decoupled from parsing their text form.

In general, there should be clarity on the responsibility of each
component, and its interactions with other parts. That makes the project
easier to maintain, test and modify. This is why concerns are separated,
e.g. `is this update authenticated` is separate from `what does this update
contain` or `inform NRTM clients of this change`. Interactions between
components should (where possible) not be dependent on existing query
or update mechanisms. We also aim to avoid repetition in e.g. query parsing
by reusing existing components while maintaining clarity and readability
of the code.

Being a Python project, it aims to follow a lot of concepts from
`The Zen of Python`_

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

The core modules are:

* ``irrd.server.whois`` deals with TCP socket handling and extracting
  individual queries. In multi-command mode, it also keeps track which
  queries are open and ensures their replies are correctly sent.
  Individual queries are passed to ``irrd.query`` for execution.
* ``irrd.query`` receives a single query in whois text form (or, in the
  future, a different format). It parses this and then instantiates
  an object that, with the parameters, will execute the query and return
  the matching objects.
* ``irrd.updates`` receives update requests, either by e-mail or TCP sockets.
  These are first parsed into individual submitted objects, along with their
  metadata like PGP signatures. The object is parsed and has the primary key
  and other values extracted by ``irrd.rpsl``. Each change is validated for
  authentication, which probably involves retreiving additional objects from
  the database. This state is then further processed by a notification handler,
  which resolves which notifications should be sent to whom, and sends them.
* ``irrd.db`` handles any interaction with the database. This is a fairly thin
  layer, and serves to abstract the underlying database somewhat from the rest
  of IRRD.
* ``irrd.rpsl`` handles RPSL objects along with their syntax, metadata,
  validation and extraction of values like primary keys. It is used when
  processing updates, and *may* also be used when returning objects,
  depending on design choices in the database.
* ``irrd.nrtm.server`` and ``irrd.nrtm.client`` will be included in more detail
  later. Likely, the client will push incoming changes to objects to a
  simplified path through ``irrd.updates``, and store some metadata about the
  mirror status in the database directly.
  The NRTM server will likely also receive notifications of all committed
  updates, and retrieve information for database dumps from the database
  directly. Updates will have to be stored in the database with a serial
  also (which most likely fits in ``irrd.updates``),
  to allow replaying them to NRTM clients.

.. [#] This diagram was made with `draw.io`_, and the source file is `part of this repo`_.

.. _The Zen of Python: https://www.python.org/dev/peps/pep-0020/#id3
.. _draw.io: https://www.draw.io/
.. _part of this repo: _static/architecture.drawio
