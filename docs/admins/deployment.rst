==========
Deployment
==========

This document details install and deploying a new instance of IRRd,
or upgrading from a legacy IRRd installation.

.. important::
    For upgrades from a legacy version of IRRd, also read the
    :doc:`migration notes </admins/migrating-legacy-irrd>`.
    For upgrades from previous versions of IRRd 4, also read
    the release notes between your new and old versions.

.. contents::
   :backlinks: none
   :local:

Requirements
------------
IRRd requires:

* Linux, OpenBSD or MacOS. Other platforms are untested, but may work.
* PyPy or CPython 3.7 through 3.11 with `pip` and `virtualenv` installed.
  PyPy is slightly recommended over CPython (the "default" Python interpreter),
  due to improved performance, in the order of 10% for some queries,
  and even higher for some GraphQL queries. However, CPython remains fully
  supported, and CPython may be the better option for you if it is easier to
  install on your deployment platform.
* A recent version of PostgreSQL. Versions 9.6, 11.16, 13.7, 15.0 are all
  tested before release. 11 or higher is strongly recommended, due to faster
  database migrations during upgrades.
* Redis 5 or newer.
* At least 32GB RAM
* At least 4 CPU cores
* At least 150GB of disk space (SSD recommended)

Depending on your needs from IRRd, you may be able to run with
fewer resources. This depends on how much data you intend to load,
and your query load.

A number of other Python packages are required. However, those are
automatically installed in the installation process.

You may need to install other packages on your OS to build IRRd's
dependencies. That includes developer packages for Python, Redis
and PostgreSQL. You will also need a Rust compiler.

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
the URL would be: ``postgresql://irrd:irrd@localhost:5432/irrd``.

You need to change a few PostgreSQL settings from their default:

* ``random_page_cost`` should be set to ``1.0``. Otherwise, PostgreSQL is
  too reluctant to use the efficient indexes in the IRRd database, and
  will opt for slow full table scans.
* ``work_mem`` should be set to 50MB to allow PostgreSQL to do in-memory
  sorting and merging.
* ``shared_buffers`` should be set to around 1/8th - 1/4th of the system
  memory to benefit from caching, with a max of a few GB.
* ``max_connections`` may need to be increased from 100. Generally, there
  will be one open connection for:
  * Each permitted whois connection
  * Each HTTP worker
  * Each running mirror import or export process
  * Each RPKI or scope filter update process
  * Each run of ``irrd_load_database``
  * Each run of ``irrd_submit_email``
  * Each open WebSocket connection for the :doc:`event stream </users/queries/event-stream>`

* ``log_min_duration_statement`` can be useful to set to ``0`` initially,
  to log all SQL queries to aid in debugging any issues.
  Note that initial imports of data produce significant logs if all queries
  are logged - importing 1GB of data can result in 2-3GB of logs.

The transaction isolation level should be set to "Read committed". This is
the default in PostgreSQL.

The initial database will be in the order of three times as large as the
size of the RPSL text imported.

.. important::

    The PostgreSQL database is the only source of IRRd's data.
    This means you need to run regular backups of the database.
    It is also possible to restore data from recent exports,
    but changes made since the most recent export will be lost.

.. _deployment-redis-configuration:

Redis configuration
-------------------
Redis is required for communication and persistence between IRRd's processes.
IRRd releases are tested on Redis 5, 6 and 7.
Beyond a default Redis installation, it is recommended to:

* Increase ``maxmemory`` to 1GB (no limit is also fine). This is a hard
  requirement - IRRd will exceed the default maximum memory otherwise.
* Disable snapshotting, by removing all ``save`` lines from the
  Redis configuration. IRRd always reloads the existing data upon startup
  of restart of either IRRd or Redis, and therefore Redis persistence
  is not needed.
* Enable unix socket support with the ``unixsocket`` configuration
  option in Redis, and using a unix socket URL in the ``redis_url``
  configuration in IRRd. This improves performance.

IRRd will recover from a Redis restart, but certain queries may fail
while Redis is unavailable.

Installing IRRd
---------------
To contain IRRd's dependencies, it is recommended to install it
in a Python virtualenv. If it is entirely sure that no other
Python work will be done, including different versions of IRRd
on the same host, this step can be skipped, but this is not
recommended.

Create the virtualenv with a command like this for PyPy::

    pypy3 -m venv /home/irrd/irrd-venv

Or, like this for CPython::

    python3 -m venv /home/irrd/irrd-venv

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
which has its own documentation. Place the config file
in ``/etc/irrd.yaml``, or configure another path with the
``--config`` parameter.


Adding a new empty source
~~~~~~~~~~~~~~~~~~~~~~~~~
To create an entirely new source without existing data, add
an entry and mark it as authoritative, and (if desired) enable
journal keeping::

    sources:
        NEW-SOURCE:
            authoritative: true
            keep_journal: true

This new source may not be visible in some status overviews until
the first object has been added. Exports are also skipped until
the source has a first object.


.. _deployment-database-upgrade:

Creating tables
---------------
IRRd uses database migrations to create and manage tables. To create
the SQL tables, "upgrade" to the latest version::

    /home/irrd/irrd-venv/bin/irrd_database_upgrade

The same command is used to upgrade the database after upgrading IRRd.

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
* ``log.logfile_path``, which should either exist with write permissions
  for the irrd user, or the irrd user should have write access to the
  directory. Note that if you use log rotation, you must ensure a new
  file with proper permissions is created before IRRd writes to it,
  or give write access to the directory.
* ``piddir``

IRRd typically binds to port 43 for whois, which is a privileged port.
To support this, start IRRd as root, and set the ``user`` and ``group``
settings in the config file. IRRd will drop privileges to this user/group
right after binding to the whois port. IRRd will refuse to run as root
if ``user`` and ``group`` are not set.

Alternatively, you can run IRRd on non-privileged ports and use IPtables
or similar tools to redirect connections from the privileged ports.


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

IRRd can be stopped by sending a SIGTERM signal. A SIGUSR1 will log a
traceback of all threads in a specific IRRd process.


.. _deployment-https:

HTTPS services configuration
----------------------------
By default, the HTTP interface runs on ``127.0.0.1:8000``. It is strongly
recommended to run a service like nginx in front of this, to support
and default to TLS connections.

A sample nginx configuration could initially look as follows
(plain HTTP to begin, HTTPS to follow)::

    http {
        include       mime.types;
        default_type  application/octet-stream;

        gzip on;
        gzip_types application/json text/plain application/jsonl+json;

        map $http_upgrade $connection_upgrade {
            default upgrade;
            ''      close;
        }
        server {
            server_name  [your hostname];
            listen       80;
            listen       [::]:80;

            location / {
                proxy_set_header Host $http_host;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection $connection_upgrade;
                proxy_read_timeout 900;
                proxy_connect_timeout 900;
                proxy_send_timeout 900;
                proxy_redirect off;
                proxy_buffering off;
                proxy_pass http://127.0.0.1:8000;
                add_header Server $upstream_http_server;
            }
        }
    }

Then, update this configuration to use HTTPS by running
``certbot --nginx``, which is available on most platforms,
to generate the right certificates from LetsEncrypt and update the
configuration to enable HTTPS, including redirects from plain HTTP.

You can also use other services or your own configuration. You will likely
need to increase some timeouts for slower queries. Enabling GZIP compression
for ``text/plain``, ``application/json`` and
``application/jsonl+json`` responses is recommended, for other responses
compression should be disabled.
If your service runs on a different host, set
``server.http.forwarded_allow_ips`` to let IRRd trust the
``X-Forwarded-For`` header.

.. warning::
    While running the HTTP services over plain HTTP is possible, using
    HTTPS is strongly recommended, particularly so that clients can verify
    the authenticity of query responses.

Logrotate configuration
-----------------------
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
---------------------

The following configuration can be used to run IRRd under systemd,
using setcap, to be created in ``/lib/systemd/system/irrd.service``::

    [Unit]
    Description=IRRD4 Service
    Wants=basic.target
    Requires=redis-server.service postgresql@11-main.service
    After=basic.target network.target redis-server.service postgresql@11-main.service

    [Service]
    Type=simple
    WorkingDirectory=/home/irrd
    User=root
    PIDFile=/home/irrd/irrd.pid  # must match piddir config in the settings
    ExecStart=/home/irrd/irrd-venv/bin/irrd --foreground
    Restart=on-failure
    ExecReload=/bin/kill -HUP $MAINPID

    [Install]
    WantedBy=multi-user.target
    WantedBy=redis-server.service
    WantedBy=postgresql@11-main.service

If you are not using PostgreSQL 11, you need to amend the service name
``postgresql@11-main.service`` in both the ``Requires=`` and ``WantedBy=``
directive.

Please note that the combination of ``Requires=`` and ``WantedBy=`` in
this unit file creates an indirect dependency between the service units
of Redis and PostgreSQL, if ``irrd.service`` is enabled.
This means that if you start either PostgreSQL or Redis, all three
services are started, which might be somewhat surprising.
This behaviour is needed for IRRd to be (re)started after (unattended)
upgrades of PostgreSQL or Redis.

Then, IRRd can be started under systemd with::

    systemctl daemon-reload
    systemctl enable irrd
    systemctl start irrd

Errors
------

Errors will generally be written to the IRRd log, or in the console, if
the config file could not be loaded.

Processing email changes
------------------------
To process incoming requested changes by email, configure a mail server to
deliver the email to the ``irrd_submit_email`` command.

When using the virtualenv as set up above, the full path is::

    /home/irrd/irrd-venv/bin/irrd_submit_email

A ``--config`` parameter can be passed to set a different configuration
file path. Results of the request are sent to the sender of the request,
and :doc:`any relevant notifications are also sent </users/database-changes>`.

.. note::
    As a separate script, `irrd_submit_email` **always acts on the current
    configuration file** - not on the configuration that IRRd started with.
