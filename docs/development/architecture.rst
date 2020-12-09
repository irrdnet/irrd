========================
Architecture / processes
========================

This document describes the general architecture of IRRd, and some of the
most important processes that take place in each component.


Process management
------------------

IRRd uses multiple processes to utilise multiple cores on servers.
It is started from ``irrd.daemon.main``, installed by setup.py
as the ``irrd`` command.

First, the process is daemonised, and then a pidfile is secured.
IRRd then starts a number of sub processes:

* The whois server process. This binds to the whois port, and then
  starts a number of worker child processes that handle connections.
* The preload manager, which listens on Redis pubsub for a message
  to update the preload store in Redis.
* The HTTP server process. This has uvicorn, the ASGI server, start
  a number of worker child processes.

After that, the main process has a number of tasks:

* Every 15 seconds, it calls the ``MirrorScheduler`` to start any
  mirror imports or exports. Each of these runs in a new child
  process.
* If a SIGHUP is received, it validates the configuration. If it is valid,
  it sends another SIGHUP to each child process, to have them reload their
  configuration as well.
* If a SIGTERM is received, IRRd should shut down. Mirror scheduling calls
  are stopped, and a SIGTERM is sent to each child process. If the
  processes do not finish after 3 seconds, a SIGKILL is sent.


Database handling
-----------------
The PostgreSQL database stores all persistent IRRd data. Therefore,
almost every other component interacts with it. However, no component
connects directly to the database, this is done through
``irrd.storage.database_handler.DatabaseHandler``.

The database handler manages important tasks, especially for processes
that write data:

* Starts and commits transactions on request
* Handles upserting of new/modified RPSL objects with an internal buffer
  for improved performance.
* Handles inserting ROA objects in a single batch.
* Handles updating the RPKI and scope filter status.
* Handles creating journal entries, by passing them to the
  ``DatabaseStatusTracker``.
* Automatic connection refresh for read-only handler instances.

All major processes, like a mirror import, use a single transaction.
This ensures that the entire process fails or succeeds, rather than
storing partial data. This also means they can pick up a consistent
state after an IRRd restart.

Most processes like mirror imports open a database connection when they
start, and close it when they are done. However, processes that handle
user queries keep a long-running connection open to reduce latency.
If the database connection is lost, and the ``DatabaseHandler`` instance
was configured as read only, it is automatically refreshed and another
attempt is made to execute the query. This provides low latency and
recovery from PostgreSQL connection loss.

Database status tracker
^^^^^^^^^^^^^^^^^^^^^^^
The ``DatabaseStatusTracker`` creates journal entries and updates
statistics for the database, like the newest serial seen. It only records
journal entries if journaling is enabled for a specific source.

The database handler only passes objects to the status tracker if the object is
:doc:`RPKI </admins/rpki>` valid or not_found, and is
in scope for the :doc:`scope filter </admins/scopefilter>`.

When the scope filter or RPKI status changes for existing objects,
the database handler updates their status in the database, and calls the
status tracker to record a deletion or addition of the newly visible/invisible
objects.

Queries
^^^^^^^
The ``irrd.storage.queries`` module contains a number of classes that help
with constructing SQL queries for IRRd data. Their purpose it to provide a
relatively simple interface, which internally generates the right
SQL statements. Some are rather small, like ``ROADatabaseObjectQuery``,
which only has one filter option. Others have many more options, like
``RPSLDatabaseQuery``. These objects can be passed to the database handler
for execution.


Preloading
----------

IRRd uses preloading of certain data to improve latency on performance
critical queries. This code is in ``irrd.storage.preload``. It relies
heavily on Redis. Currently it preloads all prefixes originated by each
ASN, split by RPSL source. There are a few steps involved:

* The database handler tracks the object classes of RPSL objects that
  have been upserted or deleted.
* When the transaction is committed, the handler will signal the
  preloader with the modified object classes.
* If the object classes are relevant (currently route(6)), the preloader
  sends a pubsub message over Redis.
* The ``PreloadStoreManager`` process receives the message and starts
  a ``PreloadUpdater`` thread. If one is already running, it starts
  a second one, which will be locked waiting for the first one.
  If there are already two running, it will do nothing - the change
  will be picked up already by the updater that hasn't started yet.
* The ``PreloadUpdater`` thread loads all route(6) objects and
  creates a dict with all prefixes originated per ASN per source.
* The store manager stores this data in Redis, and sends a different
  pubsub message.
* Each process that handles user queries listens to this second pubsub
  message, with a ``PersistentPubSubWorkerThread``, and loads the
  data from Redis into a local dict.
* Each process that handles user queries uses the local dict through
  their ``Preloader`` object.

The reason for a two step process is that the first step, getting the
objects from the database, is rather slow, in the order of 30-60 seconds.
The second process, pulling data from Redis into local memory, takes around
one second - and this is the part that needs to be done in every query
processing worker. Querying directly from Redis was found to have too
much latency.


Query processing
----------------
IRRd has :doc:`three entry points </users/queries/index>` for receiving queries
from users: raw TCP whois, whois over HTTP, and GraphQL over HTTP.

Latency is critical for some queries: for running their configuration tool,
some users may run tens of thousands of queries, sometimes over one connection,
sometimes each in their own connection.
The most performance critical queries are querying prefixes announced by
an AS, ASes in an AS-set, and prefixes announced by an AS-SET.

HTTP sockets
^^^^^^^^^^^^
For HTTP requests, IRRd starts a uvicorn ASGI server, and uses the
Starlette framework for request routing. GraphQL is handled by an Ariadne
sub-app. This code is in ``irrd.server.http``, with the GraphQL specific
code in ``irrd.server.graphql``. By using a standard HTTP server,
IRRd does very little HTTP handling itself.

Whois sockets
^^^^^^^^^^^^^
The whois server requires a custom implementation, which is in
``irrd.server.whois``. It starts a number of ``WhoisWorker`` instances.
A single listener accepts TCP connections, adds them to a queue, where
it is picked up by the first available workers.

The worker mainly deals with keeping a database connection open,
connection timeouts, and other socket handling.

Query handling
^^^^^^^^^^^^^^
Whois queries, whether received over HTTP or TCP, are mainly handled
by a ``WhoisQueryParser``. This deals with extracting the query.
and extracting validating the parameters.
The result is a ``WhoisQueryResponse``, which can translate itself into
plain text depending on a number of parameters, which is then sent
as a reply to the user.

Most of the work is done in
``irrd.server.query_resolver.QueryResolver``. For some queries this is a
fairly direct translation to an ``RPSLDatabaseQuery``. The most complex
part is recursively resolving RPSL sets.
The query resolver keeps state, for example when a user runs a query after
first restricting the included sources or setting an object class filter.
Therefore, a single instance is only used for a single connection.

GraphQL resolving
^^^^^^^^^^^^^^^^^
The :doc:`GraphQL interface </users/queries/graphql>` uses the Ariadne framework.
Important components are
the schema generator, schema builder, and resolvers.

The generator in ``irrd.server.graphql.schema_generator.SchemaGenerator``
generates the text of the GraphQL schema. This always has the same result
if no code changes are made - it is not configurable. The purpose is to
keep the object definitions in ``irrd.rpsl`` as the single source of truth.

This schema is then tied to resolvers in
``irrd.server.graphql.schema_builder``. This is how Ariadne knows which
methods to call for which queries.

The resolvers are in ``irrd.server.graphql.resolvers``. Many directly
generate ``RPSLDatabaseQuery`` objects, but the ``QueryResolver`` is used
for resolving RPSL sets and a few other tasks.


Processing updates
------------------
IRRd accepts :doc:`updates to authoritative objects </users/database-changes>`
in two ways: a small HTTP interface, or email, through the
``irrd_submit_email`` command.

In the latter case, the email is parsed first through ``irrd.utils.email``.
This includes extracting the right body, and any valid PGP signatures.

In both cases, the change is then submitted to
``irrd.updates.handler.ChangeSubmissionHandler``. This splits the update
into individual ``irrd.updates.parser.ChangeRequest`` objects, each of
which is a single request to add/update/delete a single RPSL object.

The change submission handler also deals with resolving dependent objects,
e.g. when a user adds objects A and B which depend on each other,
this should be valid. But if the creation of B fails for some reason,
this should in turn fail the creation of A. This can continue several layers
deep with chained dependencies. As a result, the handler will loop
through the validation steps multiple times until a consistent result
is achieved.

The change request object performs a number of steps:

* Determine whether the newly submitted object is valid RPSL.
* Retrieve any existing object for the same primary key.
* Validate the change for references to or from other objects,
  authentication, and not being RPKI invalid or out of scope.

  This uses the validators in ``irrd.updates.validators``.
  The authentication validator will retrieve all relevant mntners for a
  particular change, and then attempt to pass an authentication method on
  one of them, given the authentication data provided. In addition,
  ``ChangeSubmissionHandler`` provides it with context on which mntner
  objects may be new in this same submission, which therefore can't be found
  in the database and will require special handling.

  The reference validator checks that all referenced objects exist, or in case
  of deletions, whether there are no more references to the object.
  Also here, ``ChangeSubmissionHandler`` provides context on the current
  submission, making it possible to delete two objects that depend on each
  other, in one submission. The information on the references between objects
  is provided by the RPSL Python objects from ``irrd.rpsl``.
* Collate who should be notified of the change on success or
  authentication failure.
* Save the change to the database.
* Generate a human-readable or JSON report.

Updates to objects may involve a number of notifications, and a single
submission may require notifications to the same or different destinations.
For each authentication check, ``AuthValidator`` provides all potentially
relevant `mnt-nfy` and `upd-to` attributes on mntners and ``ChangeRequest``
aggregates the correct one of these two options, depending on validation
status, along with `notify`. This is then aggregated in
``ChangeSubmissionHandler`` to ensure no more emails are sent than needed.

All objects submitted to IRRd in this way are processed with
:doc:`strict object validation </admins/object-validation>`.


Mirroring
---------

The ``irrd.mirroring`` module deals with
:doc:`mirroring services </users/mirroring>`. This included mirroring other
sources, and offering mirroring of sources known to IRRd.

This process starts with ``irrd.mirroring.scheduler.MirrorScheduler``.
Called every 15 seconds, this class looks which mirror processes should
run, and starts them if there is no existing process running.

Mirroring usually comes in two forms: importing or exporting a full
dump of all RPSL objects from/to a file, and NRTM, which handles
incremental changes since a certain serial. The implementation of
NRTM is done through special ``-g`` whois queries.

Mirroring services for others
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The ``irrd.mirroring.mirror_runners_export.SourceExportRunner`` generates
a full dump of all RPSL objects for a certain source.

NRTM queries through IRRd are whois queries, so their entry point is the
``WhoisQueryParser``. After validation of parameters and access rights,
the NRTM data is generated by ``irrd.mirroring.nrtm_generator.NRTMGenerator``.
This class queries the journal for the specific source, does validation
of the requested serials, and generates an NRTM compliant output.

Mirroring other sources
^^^^^^^^^^^^^^^^^^^^^^^
The starting point is
``irrd.mirroring.mirror_runners_import.RPSLMirrorImportUpdateRunner``.
This class looks at the current local state, and determines whether
updates should be retrieved from NRTM, or a full new file import.

A full file import is done by ``RPSLMirrorFullImportRunner``. It discards
all local data for the source, and loads one or more files with RPSL data.
If needed, they are downloaded and/or unzipped first.
The actual parsing and importing is then done by
``irrd.mirroring.parsers.MirrorFileImportParser``, once per file.

If updates should be retrieved over NRTM, the runner will call
``NRTMImportUpdateStreamRunner``, which retrieves the NRTM update data
from the NRTM source. The NRTM data is then parsed and validated by
``NRTMStreamParser``, which results in a number of ``NRTMOperation``
objects, each of which is then saved to the database.

A special case is ``irrd.mirroring.parsers.MirrorUpdateFileImportParser``.
Similar to ``MirrorFileImportParser``, it processes a single file with
RPSL data. However, instead of discarding all local data, it takes this file
as the new state of the database, determines the difference between that
and the current SQL database, and generates journal entries. This allows
administrators to generate a synthesised NRTM stream which can be used
for mirroring. It is available through the ``irrd_update_database`` command.


RPKI and scope filter
---------------------
:doc:`RPKI integration </admins/rpki>` and
:doc:`scope filtering </admins/scopefilter>` are quite similar in design.

The ``RPSLMirrorImportUpdateRunner`` periodically starts a
``irrd.mirroring.mirror_runners_import.ROAImportRunner`` process,
and starts a ``ScopeFilterUpdateRunner`` every time the scope filter
configuration has changed.

The ROA import runner follows a few steps:

* Download the latest ROA JSON.
* Import the ROA data with ``irrd.rpki.importer.ROADataImporter``. This
  generates pseudo-RPKI objects and stores ROAs in their specific SQL table.
  Entries from a SLURM file can also be read and imported.
* Call ``irrd.rpki.validators.BulkRouteROAValidator`` to validate all
  current route(6) objects, and determine for which objects the RPKI
  status has changed.
* Pass the objects for which the RPKI status has changed to the database
  handler, which will update the local state and create journal entries
  if needed.
* Use ``irrd.rpki.notifications`` to send notifications to owners of
  newly invalid authoritative objects, if enabled.

The ``BulkRouteROAValidator`` is designed to be efficient when validating
many routes, because it keeps an efficient internal state, but has a
startup cost. Processes like NRTM imports and authoritative updates use
``SingleRouteROAValidator`` which queries the database directly.

The ``ScopeFilterUpdateRunner`` is simpler, as its inputs are in
the configuration file and are small. The steps are:

* Call ``irrd.scopefilter.validators.ScopeFilterValidator`` to validate all
  current route(6) objects, and determine for which objects the
  status has changed.
* Pass the objects for which the status has changed to the database
  handler, which will update the local state and create journal entries
  if needed.

The same ``ScopeFilterValidator`` is used for validating single route
objects, as it has no startup cost.


RPSL parsing and validation
---------------------------

All RPSL parsing and validation takes places in ``irrd.rpsl``. This has
a class for each supported RPSL object class, and an extensive parser
to read RPSL text. It also extracts metadata, like the relevant prefix
or origin from a route object, which is stored in separate columns
in the SQL database.

This module is the single source of truth for the structure of RPSL
objects, and is used in any place where RPSL objects are parsed.
The GraphQL interface also uses it to generate GraphQL schemas.

The particulars of object validation are
:doc:`documented in more detail </admins/object-validation>`.

The Python representations of RPSL objects in this module also provide
contextual information on the relation between objects. Some, like
``RPSLMntner``, contain additional logic such as validating passwords against
a mntner object.


Configuration
-------------

The configuration module in ``irrd.conf`` provides other modules
access to the IRRd configuration. It loads a default config,
followed by the user's config file. A SIGHUP will reload the configuration,
but only after all checks have passed on the new config. However, some
settings are only read on startup, and therefore will not take effect
until a restart.

The different settings and when they take effect are
:doc:`listed in the configuration documentation </admins/configuration>`.


Scripts
-------
This module contains scripts intended to be run from the command line.
They are installed by setup.py, with the prefix ``irrd_``.

* ``database_downgrade`` and ``database_upgrade`` are small wrappers
  around Alembic to migrate the database between versions.
* ``load_database`` and ``update_database`` import RPSL data from local files.
* ``mirror_force_reload`` is a small wrapper to set the ``force_reload`` flag,
  which forces ``RPSLMirrorImportUpdateRunner`` to do a full reload rather
  than NRTM updates.
* ``submit_email`` will read an email with updates from stdin and process
  them. This is the expected entry point for processing incoming email.
* ``submit_changes`` will read direct RPSL submissions from stdin and process
  them. It does not support PGP.
* ``rpsl_read`` reads files with RPSL data, and inserts them into the
  database. It is mainly intended for testing, as it does not include
  aspects like source status metadata updates.
* ``query_qa_comparison`` is used for QA tests in query handling.

Note that as separate scripts, they **always acts on the current configuration
file** - not on the configuration that IRRd started with.
The latter two scripts are not included in distributions.

Utilities
---------
The ``irrd.utils`` module contains a few parts used in other places:

* A class for extracting text and PGP metadata from plain and multipart
  emails, along with other metadata.
* A wrapper around gpg to validate an inline or PGP/MIME signature.
* A small support layer for multiprocessing.
* Sample RPSL objects used for tests.
* Text utilities for working with RPSL paragraphs and lines, stripping
  password hashes, and text conversions.
* Validators for AS numbers and change submissions.
* A small whois client, used by the status info page.
