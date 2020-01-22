==========
Deployment
==========

This document details install and deploying a new instance of IRRd,
or upgrading from a legacy IRRd installation.
For upgrades from a legacy version of IRRd, please read the
:doc:`migration notes </admins/migrating-legacy-irrd>` for relevant
changes.

.. contents:: :backlinks: none

Requirements
------------
IRRd requires:

* Linux or MacOS. Other platforms are untested, but may work.
* Python 3.6, with `pip` and `virtualenv` installed.
  At this point, 3.7 has had limited testing.
* A recent version of PostgreSQL. Versions 9.6 and 10.5 have been
  extensively tested.
* At least 32GB RAM
* At least 4 CPU cores
* At least 100GB of disk space (SSD recommended)

A number of other Python packages are required. However, those are
automatically installed in the installation process.


PostgreSQL configuration
------------------------
IRRd requires a PostgreSQL database to store IRR and status data.
Here's an example of how to correctly create the database and assign
the necessary permissions, to be run as a superuser::

    CREATE DATABASE irrd;
    CREATE ROLE irrd WITH LOGIN ENCRYPTED PASSWORD 'irrd';
    GRANT ALL PRIVILEGES ON DATABASE irrd TO irrd;
    \c irrd
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

The `pgcrypto` extension is used by some IRRd tables, and has to be created
by a superuser on the new database. As IRRd manages its own tables, it needs
all privileges on the database.

The database, username and password have to be configured in the
``database_url`` :doc:`setting </admins/configuration>`. In this example,
the URL would be ``postgresql://irrd:irrd@localhost:5432/irrd``.

A few PostgreSQL settings need to be changed from their default:

* ``random_page_cost`` should be set to ``1.0``. Otherwise, PostgreSQL is
  too reluctant to use the efficient indexes in the IRRd database, and
  will opt for slow full table scans.
* ``work_mem`` should be set to 50MB to allow PostgreSQL to do in-memory
  sorting and merging.
* ``shared_buffers`` should be set to around 1/8th - 1/4th of the system
  memory to benefit from caching, with a max of a few GB.
* ``max_connections`` may need to be increased from 100. Generally, there
  will be one open connection for:
  * Each open whois connection
  * Each running mirror import and export process
  * Each RPKI update process
  * Each run of ``irrd_load_database``
  * Each run of ``irrd_submit_email``
* ``log_min_duration_statement`` can be useful to set to ``0`` initially,
  to log all SQL queries to aid in debugging any issues.
  Note that initial imports of data produce significant logs if all queres
  are logged - importing 1GB of data can result in 2-3GB of logs.

The database will be in the order of three times as large as the size of
the RPSL text imported.

.. important::

    The PostgreSQL database is the only source of IRRd's data.
    This means backups of the database should be run regularly.
    It is also possible to restore data from recent exports,
    but changes made since the most recent export will be lost.

.. _deployment-redis-configuration:

Redis configuration
-------------------
Redis is required for communication and persistence between IRRd's processes.
Beyond a default Redis installation, it is recommended to:

* Disable snapshotting, by removing all ``save`` lines from the
  Redis configuration. IRRd always reloads the existing data upon startup
  of restart of either IRRd or Redis, and therefore Redis persistence
  is not needed.
* Enable unix socket support with the ``unixsocket`` configuration
  option in Redis, and using a unix socket URL in the ``redis_url``
  configuration in IRRd. This improves performance.

IRRd will recover from a Redis restart, but certain queries mail fail
while Redis is unavailable.

Installing IRRd
---------------
To contain IRRd's dependencies, it is recommended to install it
in a Python virtualenv. If it is entirely sure that no other
Python work will be done, including different versions of IRRd
on the same host, this step can be skipped, but this is not
recommended

Create the virtualenv with a command like this::

    virtualenv -p python3 /home/irrd/irrd-venv

To run commands inside the virtualenv, use either of::

    /home/irrd/irrd-venv/bin/<command>

    # or:

    # Persists. Leave the venv with `deactivate`
    source /home/irrd/irrd-venv/bin/activate
    <command>

To install the latest version of IRRd inside the virtualenv, use pip3::

    /home/irrd/irrd-venv/bin/pip3 install irrd

Instead of ``irrd``, which pulls the latest version from PyPI, it's also
possible specify a specific version, e.g. ``irrd==4.0.1``, or provide a
path to a local distribution file.


Creating a configuration file
-----------------------------
IRRd uses a :doc:`YAML configuration file </admins/configuration>`,
which has its own documentation. The config file should either be placed
in ``/etc/irrd.yaml``, or another path can be set in the
``--config`` parameter.


Adding a new empty source
~~~~~~~~~~~~~~~~~~~~~~~~~
To create an entirely new source without existing data, add
an entry and mark it as authoritative, and probably enable
journal keeping::

    sources:
        NEW-SOURCE:
            authoritative: true
            keep_journal: true

This new source may not be visible in some status overviews until
the first object has been added. Exports are also skipped until
the source has a first object.

Migrating existing data
~~~~~~~~~~~~~~~~~~~~~~~
Mirrored sources, where the current production instance is not
authoritative, can also be configured as a mirror in the new IRRd instance.
Adding the source to the config, along with the settings for initial downloads
and (where applicable) NRTM, will cause them to be automatically
downloaded, imported, and further updates to be received over NRTM.

Current authoritative sources can also be configured as a mirror, of
the current production instance, with ``keep_journal`` enabled.
This is the most efficient way to import existing authoritative data.

.. admonition:: Data validation and key-certs

    Validation for objects from mirrors is
    :doc:`less strict than authoritative data </admins/object-validation>`
    submitted directly to IRRd. With this migration process, objects
    may be migrated that are invalid under strict validation. This is
    practical, because it allows migrating legacy objects, which users
    will be forced to correct only when they try to submit new changes.

    **However, if the data to be migrated contains key-cert objects,
    a specific setting should be enabled** on the soon-to-be
    authoritative source:
    ``strict_import_keycert_objects``.
    This setting forces stricter validation for `key-cert` objects,
    which may cause some to be rejected. However, it is essential when
    mirroring data for which the new IRRd instance will soon be authoritative,
    as only in strict validation the PGP keys are loaded into the local
    gpg keychain. This loading is required to be able to use them for
    authentication once the new IRRd instance is authoritative.

Once these mirrors are running, and you're not seeing any issues,
the general plan for switching over to a new IRRd v4 instance would be:

* Block update emails.
* Ensure an NRTM update has run so that the instances are in sync
  (it may be worthwhile to lower ``import_timer``)
* Remove the mirror configuration from the new IRRd 4 instance for
  any authoritative sources.
* Set the authoritative sources to ``authoritative: true`` in the config.
* Redirect queries to the new instance.
* Redirect update emails to the new instance.
* Ensure published exports are now taken from the new instance.

Depending on the time that the authoritative source has been mirrored
prior to migrating, the migration may be fluent for others that
mirror data from the new IRRd 4 instance. In other cases, they may
need to do a new full import, similar to any other scenario where they
have too much lag to use NRTM.

.. note::
    During an initial import of many large sources at the same time, IRRd's
    memory use may reach 3-4GB. During this import, query performance may
    be reduced. This may take around 30-45 minutes.

.. _deployment-database-upgrade:

Creating tables
---------------
IRRd uses database migrations to create and manage tables. To create
the SQL tables, "upgrade" to the latest version::

    /home/irrd/irrd-venv/bin/irrd_database_upgrade

A ``--config`` parameter can be passed to set a different configuration
file path. A ``version`` parameter can be passed to upgrade to a specific
version, the default is the latest version (`head`).


Running as a non-privileged user
--------------------------------
It is recommended to run IRRd as a non-privileged user. This user needs
read access to:

* the virtualenv
* the configuration file
* ``sources.{{name}}.import_source`` (if this is a local file)
* ``sources.{{name}}.import_serial_source`` (if this is a local file)

The user also needs write access to access to:

* ``auth.gnupg_keyring``
* ``sources.{name}.export_destination``
* ``log.logfile_path``. As IRRd creates ``log.logfile_path`` itself,
  it needs write access to the directory this file is in
* ``piddir``


.. _deployment-starting-irrd:

Starting IRRd
-------------
IRRd runs as a daemon, and can be started with::

    /home/irrd/irrd-venv/bin/irrd

Useful options:

* ``--config=<path>`` loads the configuration from a different path than the
  default ``/etc/irrd.yaml``. This must always be the full path.
* ``--foreground`` makes the process run in the foreground. If
  ``log.logfile_path`` is not set, this also shows all log output
  in the terminal.
* ``--uid=<user>`` makes the process run as a non-privileged user. However,
  this happens after binding to TCP ports, so setcap as listed below is
  the recommended method to drop privilege.

IRRd can be stopped by sending a SIGTERM signal.

.. note::
    Although ``log.logfile_path`` is not required, if it is unset and
    IRRd is started in the background, log output is lost.

Using setcap
~~~~~~~~~~~~
IRRd can drop privileges with the ``--uid`` parameter, as used in the last
section. A better option is to run the IRRd command as the non-privileged
user, and use ``setcap`` to assign that user permissions to open privileged
ports, e.g.::

    # Once, as root:
    setcap 'cap_net_bind_service=+ep' /home/irrd/irrd-venv/bin/python3
    # To run, start without --uid, as the non-privileged user
    /home/irrd/irrd-venv/bin/irrd

Logrotate configuration
~~~~~~~~~~~~~~~~~~~~~~~
The following logrotate configuration can be used for IRRd::

    /home/irrd/server.log {
        missingok
        daily
        compress
        delaycompress
        dateext
        rotate 35
        olddir /home/irrd/logs
        postrotate
            systemctl reload irrd.service > /dev/null 2>&1 || true
        endscript
    }

This assumes the ``log.logfile_path`` setting is set to
``/home/irrd/server.log``. This file should be created in the path
``/etc/logrotate.d/irrd`` with permissions ``0644``.

Systemd configuration
~~~~~~~~~~~~~~~~~~~~~

The following configuration can be used to run IRRd under systemd,
using setcap, to be created in ``/lib/systemd/system/irrd.service``::

    [Unit]
    Description=IRRD4 Service
    Wants=basic.target
    After=basic.target network.target

    [Service]
    Type=simple
    WorkingDirectory=/home/irrd
    User=irrd
    Group=irrd
    PIDFile=/home/irrd/irrd.pid  # must match piddir config in the settings
    ExecStart=/home/irrd/irrd-venv/bin/irrd --foreground
    Restart=on-failure
    ExecReload=/bin/kill -HUP $MAINPID

    [Install]
    WantedBy=multi-user.target

Then, IRRd can be started under systemd with::

    systemctl daemon-reload
    systemctl enable irrd
    systemctl start irrd

Errors
~~~~~~

Errors will generally be written to the IRRd log, or in the console, if
the config file could not be loaded.

Processing email changes
------------------------
To process incoming requested changes by email, configure a mailserver to
deliver the email to the ``irrd_submit_email`` command.

When using the virtualenv as set up above, the full path is::

    /home/irrd/irrd-venv/bin/irrd_submit_email

A ``--config`` parameter can be passed to set a different configuration
file path. Results of the request are sent to the sender of the request,
and :doc:`any relevant notifications are also sent </users/database-changes>`.

.. note::
    As a separate script, `irrd_submit_email` **always acts on the current
    configuration file** - not on the configuration that IRRd started with.
