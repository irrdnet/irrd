.. |br| raw:: html

   <br />

=============
Configuration
=============

IRRd reads its configuration from a YAML file in a specified location. Many
configuration options can be changed without restarting IRRd, but not all.

.. contents:: :backlinks: none

Example configuration file
--------------------------

.. highlight:: yaml
    :linenothreshold: 5

This sample shows most configuration options::

    irrd:
        database_url: 'postgresql://localhost:5432/irrd'

        access_lists:
            http_database_status:
                - '::/32'
                - '127.0.0.1'

            generic_nrtm_access:
                - '192.0.2.0/24'

        server:
            http:
                access_list: http_database_status
                interface: '::0'
                port: 8080
            whois:
                interface: '::0'
                max_connections: 50
                port: 8043

        auth:
            gnupg_keyring: /home/irrd/gnupg-keyring/
            override_password: {hash}

        email:
            footer: 'email footer'
            from: example@example.com
            smtp: localhost
            notification_header: |
                This is to notify you of changes in the {sources_str} database
                or object authorisation failures.

                You may receive this message because you are listed in
                the notify attribute on the changed object(s), or because
                you are listed in the mnt-nfy or upd-to attribute on a maintainer
                of the object(s).

        log:
            logfile_path: /var/log/irrd/irrd.log
            level: DEBUG

        rpki:
            roa_source: https://example.com/roa.json
            roa_import_timer: 7200

        sources_default:
            - AUTHDATABASE
            - MIRROR-SECOND
            - MIRROR-FIRST
            - RPKI

        sources:
            AUTHDATABASE:
                # Authoritative database, allows local changes, full export every 2h
                authoritative: true
                keep_journal: true
                export_destination: /var/ftp/
                export_timer: 7200
                nrtm_access_list: generic_nrtm_access
            MIRROR-FIRST:
                # Run a full import at first, then periodic NRTM updates.
                authoritative: false
                keep_journal: true
                import_serial_source: 'ftp://ftp.example.net/MIRROR-FIRST.CURRENTSERIAL'
                import_source: 'ftp://ftp.example.net/mirror-first.db.gz'
                nrtm_host: rr.ntt.net
                nrtm_port: 43
                object_class_filter:
                    - as-set
                    - aut-num
                    - filter-set
                    - inet-rtr
                    - key-cert
                    - mntner
                    - peering-set
                    - route
                    - route6
                    - route-set
                    - rtr-set
            MIRROR-SECOND:
                # Every hour, a new full import will be done.
                authoritative: false
                import_source:
                    - 'ftp://ftp.example.net/mirror-second.db.as-set.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.aut-num.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.filter-set.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.route-set.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.route.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.route6.gz'
                    - 'ftp://ftp.example.net/mirror-second.db.route-set.gz'
                import_timer: 3600


Loading and reloading
---------------------

The configuration is loaded when IRRd starts. By default, IRRd looks for the
config file in ``/etc/irrd.yaml``.
A different path can be provided with the ``--config`` parameter.

If the configuration is invalid, the daemon will refuse to start.
While running, the configuration can be reloaded by sending a `SIGHUP` signal.
Most settings will take effect immediately, but some require a full restart.
If a `SIGHUP` is sent and the new configuration is invalid, errors will be
written to the logfile, but IRRd will keep running with the last valid
configuration. A successful reload after a `SIGHUP` is also logged.

.. important::

    Not all configuration errors are caught when reloading, such as making IRRd
    bind to a TCP port that is already in use. An incorrect password for the
    PostgreSQL database is only detected when IRRd restarts and attempts
    to connect.

.. note::
    As a separate script, `irrd_submit_email`, the handler for email submissions
    by IRRd users, and `irrd_load_database` for manually loading data,
    **always act on the current configuration file** - not on
    the configuration that IRRd started with.


Configuration options
---------------------

Database
~~~~~~~~
* ``database_url``: a RFC1738 PostgreSQL database URL for the database used by
  IRRd, e.g. ``postgresql://username:password@localhost:5432/irrd`` to connect
  to `localhost` on port 5432, database `irrd`, username `username`,
  password `password`.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.

Servers
~~~~~~~
* ``server.[whois|http].interface``: the network interface on which the whois or
  HTTP interface will listen
  |br| **Default**: ``::0``.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.[whois|http].port``: the port on which the whois or HTTP interface
  will listen.
  |br| **Default**: ``43`` for whois, ``80`` for HTTP.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.[whois|http].access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted access. If not
  defined, all access is permitted for whois, but all access is denied for HTTP.
  |br| **Default**: not defined, all access permitted for whois, all access
  denied for HTTP.
  |br| **Change takes effect**: after SIGHUP.
* ``server.whois.max_connections``: the maximum number of simultaneous whois
  connections permitted.
  |br| **Default**: ``50``.
  |br| **Change takes effect**: after SIGHUP. Existing connections will not
  be terminated.

Email
~~~~~
* ``email.from``: the `From` email address used when sending emails.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
* ``email.footer``: a footer to include in all emails.
  |br| **Default**: empty string.
  |br| **Change takes effect**:  after SIGHUP, for all subsequent emails.
* ``email.smtp``: the SMTP server to use for outbound emails.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
* ``email.notification_headers``: the header to use when sending notifications
  of (attempted) changes to addresses in `notify`, `mnt-nfy` or `upd-to`
  attributes. The string ``{sources_str}`` will be replaced with the name
  of the source(s) (e.g. ``NTTCOM``) of the relevant objects. When adding
  this to the configuration, use the `|` style to preserve newlines, as
  shown in the example configuration file above.
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
  |br| **Default**:
  |br| `This is to notify you of changes in the {sources_str} database`
  |br| `or object authorisation failures.`
  |br|
  |br| `You may receive this message because you are listed in`
  |br| `the notify attribute on the changed object(s), or because`
  |br| `you are listed in the mnt-nfy or upd-to attribute on a maintainer`
  |br| `of the object(s).`


Authentication
~~~~~~~~~~~~~~
* ``auth.override_password``: a salted MD5 hash of the override password,
  which can be used to override any
  authorisation requirements for authoritative databases.
  |br| **Default**: not defined, no override password will be accepted.
  |br| **Change takes effect**: after SIGHUP.
* ``auth.gnupg_keyring``: the full path to the gnupg keyring.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.

.. danger::

    IRRd loads keys into the gnupg keyring when `key-cert` objects are
    imported. Their presence in the keyring is then used to validate requested
    changes. Therefore, the keyring referred to by ``auth.gnupg_keyring`` can
    not be simply reset, or PGP authentications may fail.


Access lists
~~~~~~~~~~~~
* ``access_lists.{list_name}``: a list of permitted IPv4 and/or IPv6 addresses
  and/or prefixes, which will be
  permitted access for any service that refers to access list ``{list_name}``.
  IPv4 addresses and/or prefixes should not be IPv6-mapped in the access list.
  |br| **Default**: no lists defined.
  |br| **Change takes effect**: after SIGHUP, for all subsequent requests.

RPKI
~~~~
* ``roa_source``: an HTTP(s) URL to a JSON file with ROA exports, in the format
  as produced by the RIPE NCC RPKI validator. When set, this enables the
  :doc:`RPKI-aware mode </admins/rpki>`.
  |br| **Default**: not defined, RPKI-aware mode disabled.
  |br| **Change takes effect**: after SIGHUP. The first RPKI ROA import may
  take several minutes, after which RPKI-aware mode is enabled.
* ``roa_import_timer``: the time between two attempts to import the ROA
  file from ``roa_source``
  |br| **Default**: ``7200``.
  |br| **Change takes effect**: after SIGHUP.

Sources
~~~~~~~
* ``sources_default``: a list of sources that are enabled by default, or when a
  user selects all sources with ``-a``. The order of this list defines the
  search priority as well. It is not required to include all known sources in
  the default selection. If ``rpki.roa_source`` is defined, this may also
  include ``RPKI``, which contains psuedo-IRR objects generated from ROAs.
  |br| **Default**: not defined. All sources are enabled, but results are not
  ordered by source.
  |br| **Change takes effect**: after SIGHUP, for all subsequent queries.
* ``sources.{name}``: settings for a particular source. The name must be
  all-uppercase, start with a letter, and end with a letter or digit. Valid
  characters are letters, digits and dashes. The minimum length is two
  characters. If ``rpki.roa_source`` is defined, ``RPKI`` is a reserved
  source name, as it contains psuedo-IRR objects generated from ROAs.
* ``sources.{name}.authoritative``: a boolean for whether this source is
  authoritative, i.e. changes are allowed to be submitted to this IRRd instance
  through e.g. email updates.
  |br| **Default**: ``false``.
  |br| **Change takes effect**: after SIGHUP, for all subsequent requests.
* ``sources.{name}.keep_journal``: a boolean for whether a local journal is
  retained of changes to objects from this source. This journal can contain
  changes submitted to this IRRd instance, or changes received over NRTM.
  This setting is needed when offering mirroring services for this source.
  Can only be enabled when either ``authoritative`` is enabled, or both
  ``nrtm_host`` and ``import_serial_source`` are configured.
  |br| **Default**: ``false``.
  |br| **Change takes effect**: after SIGHUP, for all subsequent changes.
* ``sources.{name}.nrtm_host``: the hostname or IP to connect to for an NRTM stream.
  |br| **Default**: not defined, no NRTM requests attempted.
  |br| **Change takes effect**: after SIGHUP, at the next NRTM update.
* ``sources.{name}.nrtm_port``: the TCP port to connect to for an NRTM stream.
  |br| **Default**: 43
  |br| **Change takes effect**: after SIGHUP, at the next NRTM update.
* ``sources.{name}.import_source``: the URL or list of URLs where the full
  copies of this source can be retrieved. You can provide a list of URLs for
  sources that offer split files. Supports HTTP(s), FTP or local file URLs.
  Automatic gzip decompression is supported for HTTP(s) and FTP if the
  filename ends in ``.gz``.
  |br| **Default**: not defined, no imports attempted.
  |br| **Change takes effect**: after SIGHUP, at the next full import. This
  will only occur if this source is forced to reload, i.e. changing this URL
  will not cause a new full import by itself in sources that use NRTM.
  For sources that do not use NRTM, every mirror update is a full import.
* ``sources.{name}.import_serial_source``: the URL where the file with serial
  belonging to the ``import_source`` can be retrieved. Supports HTTP(s), FTP or
  local file URLs, in ``file://<path>`` format.
  |br| **Default**: not defined, no imports attempted.
  |br| **Change takes effect**: see ``import_source``.
* ``sources.{name}.import_timer``: the time between two attempts to retrieve
  updates from a mirrored source, either by full import or NRTM. This is
  particularly significant for sources that do not offer an NRTM stream, as
  they will instead run a full import every time this timer expires. The
  default is rather frequent for sources that work exclusively with periodic
  full imports. The minimum effective time is 15 seconds, and this is also
  the granularity of the timer.
  |br| **Default**: ``300``.
  |br| **Change takes effect**: after SIGHUP.
* ``sources.{name}.object_class_filter``: a list of object classes that will
  be mirrored. Objects of other RPSL object classes will be ignored immediately
  when encountered in full imports or NRTM streams. Without a filter, all
  objects are mirrored.
  |br| **Default**: no filter, all known object classes permitted.
  |br| **Change takes effect**: after SIGHUP, at the next NRTM update or full import.
* ``sources.{name}.export_destination``: a path to save full exports, including
  a serial file, of this source. The data is initially written to a temporary
  file, and then moved to the destination path. The export of RPSL data is always
  gzipped. If there is no serial information available (i.e. the journal is
  empty) no serial file is produced. If the database is entirely empty, an error
  is logged and no files are exported. This directory needs to exist already,
  IRRd will not create it. File permissions are always set to ``644``.
  |br| **Default**: not defined, no exports made.
  |br| **Change takes effect**: after SIGHUP, at the next ``export_timer``.
* ``sources.{name}.export_timer``: the time between two full exports of all
  data for this source. The minimum effective time is 15 seconds, and this is
  also the granularity of the timer.
  |br| **Default**: ``3600``.
  |br| **Change takes effect**: after SIGHUP
* ``sources.{name}.nrtm_access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted access to the
  NRTM stream for this particular source (``-g`` queries).
  |br| **Default**: not defined, all access denied.
  |br| **Change takes effect**: after SIGHUP, upon next request.
* ``sources.{name}.strict_import_keycert_objects``: a setting used when
  migrating authoritative data that may contain `key-cert` objects.
  See the :doc:`deployment guide </admins/deployment>` for more information.
  |br| **Default**: false
  |br| **Change takes effect**: after SIGHUP, upon next request.


For more detail on mirroring other sources, and providing mirroring services
to others, see the :doc:`mirroring documentation </users/mirroring>`.

.. caution::

    **Journal-keeping is the only full object history that is kept of the
    database, and is therefore strongly recommended to enable on
    authoritative databases to be able to reconstruct history.**

    Journal-keeping for NRTM streams is dependent on providing a single
    uninterrupted stream of updates. This stream is only kept while
    ``keep_journal`` is enabled. Disabling it while mirrors are dependent on it,
    even briefly, will cause the databases to go out of sync silently until
    the mirror runs a new full import.

.. note::

    Source names are case sensitive and must be an exact match to
    ``sources_default``, and the source attribute value in any objects imported
    from files or NRTM. E.g. if ``sources.EXAMPLE`` is defined, and
    ``sources_default`` contains ``example``, this is a configuration error.
    If an object is encountered with ``source: EXAMPLe``, it is rejected and an
    error is logged.

.. note::

    New sources added are detected after a SIGHUP. However, when adding a large
    amount of new sources, restarting IRRd is recommended. An internal pool of
    database connections is based, among other things, on the number of sources,
    and this pool size is only updated on restart. For adding one or two
    sources, the impact is insignificant and a restart is not required.


Logging
~~~~~~~
* ``log.logfile_path``: the full path where the logfile will be written. IRRd
  will attempt to create the file if it does not exist. If the file is removed,
  e.g. by a log rotation process, IRRd will create a new file in the same
  location, and continue writing to the new file. Timestamps in logs are always
  in UTC, regardless of local machine timezone.
  |br| **Default**: not defined, logs will be sent to the console.
  |br| **Change takes effect**: after full IRRd restart.
* ``log.level``: the loglevel, one of `DEBUG`, `INFO`, `WARNING`, `ERROR`,
  `CRITICAL`. The recommended level is `INFO`.
  |br| **Default**: ``INFO``.
  |br| **Change takes effect**: after SIGHUP.

Compatibility
~~~~~~~~~~~~~
* ``compatibility.ipv4_only_route_set_members``: if set to ``true``, ``!i``
  queries will not return IPv6 prefixes. This option can be used for limited
  compatibility with IRRd version 2. Enabling this setting may have a
  performance impact on very large responses.
  |br| **Default**: ``false``, IPv6 members included
  |br| **Change takes effect**: after SIGHUP, for all subsequent queries.
