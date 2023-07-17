.. |br| raw:: html

   <br />

=============
Configuration
=============

IRRd reads its configuration from a YAML file in a specified location. Many
configuration options can be changed without restarting IRRd, but not all.

The IRRd configuration file has some hierarchy, which is dot-separated in
this documentation and IRRd error messages. For example, when this
documentation mentions a setting like ``rpki.roa_source``, this refers to
a key ``roa_source`` under a key ``rpki``.

.. contents::
   :backlinks: none
   :local:
   :depth: 2



Example configuration file
--------------------------

.. highlight:: yaml
    :linenothreshold: 5

This sample shows most configuration options

.. note:: 
  Note that this is an example of what a configuration file can look like.
  Many of these settings are optional, or the value shown in this example is
  their default. This is intended as an example of syntax, not as a template
  for your own configuration.

::

    irrd:
        database_url: 'postgresql:///irrd'
        redis_url: 'unix:///usr/local/var/run/redis.sock'
        piddir: /var/run/
        user: irrd
        group: irrd
        # required, but no default included for safety
        secret_key: null

        access_lists:
            http_database_status:
                - '::/32'
                - '127.0.0.1'

            generic_nrtm_access:
                - '192.0.2.0/24'

        server:
            http:
                status_access_list: http_database_status
                interface: '::0'
                port: 8080
                url: "https://irrd.example.com/"
            whois:
                interface: '::0'
                max_connections: 50
                port: 8043

        auth:
            gnupg_keyring: /home/irrd/gnupg-keyring/
            override_password: {hash}
            webui_auth_failure_rate_limit: "30/hour"
            password_hashers:
                md5-pw: legacy

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
            roa_source: https://rpki.gin.ntt.net/api/export.json
            roa_import_timer: 3600
            pseudo_irr_remarks: |
                This AS{asn} route object represents routing data retrieved
                from the RPKI. This route object is the result of an automated
                RPKI-to-IRR conversion process performed by IRRd.

        scopefilter:
            prefixes:
                - 10.0.0.0/8
            asns:
                - 23456
                - 64496-64511
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
                rpki_excluded: true
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

IRRd will reject unknown configuration options, and fail to start or reload.

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

General settings
~~~~~~~~~~~~~~~~
* ``database_url``: a RFC1738 PostgreSQL database URL for the database used by
  IRRd, e.g. ``postgresql://username:password@localhost:5432/irrd`` to connect
  to `localhost` on port 5432, database `irrd`, username `username`,
  password `password`. Use ``postgresql://username:password@/irrd`` to connect
  to the default unix socket.
  **Connecting through a unix socket is strongly recommended**,
  for improved performance
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.
* ``readonly_standby``: a boolean for whether this instance is
  in read-only standby mode. See
  :doc:`availability with PostgreSQL replication </admins/availability-and-migration>`
  for further details. Can not be used if any source has ``authoritative``,
  ``import_source`` or ``nrtm_host`` set.
  **Do not enable this setting without reading the further documentation on standby setups.**
  |br| **Default**: ``false``.
  |br| **Change takes effect**: after full IRRd restart.
* ``redis_url``: a URL to a Redis instance, e.g.
  ``unix:///var/run/redis.sock`` to connect through a unix socket, or
  ``redis://localhost`` to connect through TCP.
  **Connecting through a unix socket is strongly recommended**,
  for improved performance
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.
* ``piddir``: an existing writable directory where the IRRd PID file will
  be written (as ``irrd.pid``).
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.
* ``user`` and ``group``: the user and group name to which IRRd will drop
  privileges, after binding to ``server.whois.port``.
  This allows IRRd to be started as root, bind to port 43, and then
  drop privileges. Both must be defined, or neither.
  Note that binding to ``server.http.port`` happens after dropping privileges,
  as the recommended deployment is to have
  :ref:`an HTTPS proxy <deployment-https>` in front. Therefore, there is no
  need for IRRd to bind to port 80 or 443.
  |br| **Default**: not defined, IRRd does not drop privileges.
  |br| **Change takes effect**: after full IRRd restart.
* ``secret_key``: a random secret string. **The secrecy of this key protects
  all web authentication.** If rotated, all sessions and tokens in emails
  are invalidated, requiring users to log in or request new password
  reset links. Rotation will **not** invalidate existing user passwords
  (only reset links), second factor authentication, or API tokens.
  Minimum 30 characters.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.


Servers
~~~~~~~
* ``server.[whois|http].interface``: the network interface on which the whois or
  HTTP interface will listen. Running the HTTP interface behind nginx or a
  similar service :ref:`is strongly recommended <deployment-https>`.
  |br| **Default**: ``::0`` for whois, ``127.0.0.1`` for HTTP.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.[whois|http].port``: the port on which the whois or HTTP interface
  will listen.
  |br| **Default**: ``43`` for whois, ``8000`` for HTTP.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.whois.access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted access. If not
  defined, all access is permitted.
  |br| **Default**: not defined, all access permitted for whois
  |br| **Change takes effect**: after SIGHUP.
* ``server.http.status_access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted access to the
  :doc:`HTTP status page </admins/status_page>`. If not defined, all access is denied.
  |br| **Default**: not defined, all access denied for HTTP status page
  |br| **Change takes effect**: after SIGHUP.
* ``server.http.event_stream_access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted access to the
  :doc:`event stream </users/queries/event-stream>` initial download and WebSocket
  stream. If not defined, all access is denied.
  |br| **Default**: not defined, all access denied for event stream.
  |br| **Change takes effect**: after SIGHUP.
* ``server.http.url``: the external URL on which users will reach the
  IRRD instance. This is used for WebAuthn security tokens.
  **Changing this URL after users have configured security tokens
  will invalidate all tokens ** - an intentional anti-phishing
  design feature of WebAuthn. The scheme must be included.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after SIGHUP.
* ``server.whois.max_connections``: the maximum number of simultaneous whois
  connections permitted. Note that each permitted connection will result in
  one IRRd whois worker to be started, each of which use about 200 MB memory.
  For example, if you set this to 50, you need about 10 GB of memory just for
  IRRd's whois server.
  (and additional memory for other components and PostgreSQL).
  |br| **Default**: ``10``.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.http.workers``: the number of HTTP workers launched on startup.
  Each worker can process one GraphQL query or other HTTP request at a time.
  Note that each worker uses about 200 MB memory.
  For example, if you set this to 50, you need about 10 GB of memory just for
  IRRd's HTTP server.
  (and additional memory for other components and PostgreSQL).
  |br| **Default**: ``4``.
  |br| **Change takes effect**: after full IRRd restart.
* ``server.http.forwarded_allowed_ips``: a single IP or list of IPs from
  which IRRd will trust the ``X-Forwarded-For`` header. This header is used
  for IRRd to know the real client address, rather than the address of a
  proxy.
  |br| **Default**: ``127.0.0.1``.
  |br| **Change takes effect**: after full IRRd restart.


Email
~~~~~
* ``email.from``: the `From` email address used when sending emails.
  Good choices for this are a noreply address, or a support inbox.
  **Never set this to an address that is directed back to IRRd, as this may
  cause e-mail loops.**
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
* ``email.footer``: a footer to include in all emails.
  |br| **Default**: empty string.
  |br| **Change takes effect**:  after SIGHUP, for all subsequent emails.
* ``email.smtp``: the SMTP server to use for outbound emails.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
* ``email.recipient_override``: override the recipient of all emails to
  this email address instead. Useful for testing setups.
  |br| **Default**: not defined, no override
  |br| **Change takes effect**: after SIGHUP, for all subsequent emails.
* ``email.notification_header``: the header to use when sending notifications
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
  |br| `the notify attribute on the changed object(s), because`
  |br| `you are listed in the mnt-nfy or upd-to attribute on a maintainer`
  |br| `of the object(s), or the upd-to attribute on the maintainer of a`
  |br| `parent of newly created object(s).`


Authentication and validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* ``auth.override_password``: a salted MD5 hash of the override password,
  which can be used to override any
  authorisation requirements for authoritative databases.
  |br| **Default**: not defined, no override password will be accepted.
  |br| **Change takes effect**: upon the next update attempt.
* ``auth.gnupg_keyring``: the full path to the gnupg keyring.
  |br| **Default**: not defined, but required.
  |br| **Change takes effect**: after full IRRd restart.
* ``auth.irrd_internal_migration_enabled``: whether users can initiate a migration
  their mntners to IRRD-INTERNAL-AUTH authentication through the web interface.
  If this is disabled after some mntners have already been migrated, those
  will remain available and usable - this setting only affects new migrations.
  |br| **Default**: disabled.
  |br| **Change takes effect**: after SIGHUP, for all subsequent attempts to
  initiate a migration.
* ``auth.webui_auth_failure_rate_limit``: the rate limit for failed
  authentication attempts through the web interface. This includes logins,
  but also other cases that request passwords. This is a moving window
  in the format of the limits_ library.
  |br| **Default**: ``30/hour``.
  |br| **Change takes effect**: after full IRRd restart.
* ``auth.password_hashers``: which password hashers to allow in mntner objects.
  This is a dictionary with the hashers (``crypt-pw``, ``md5-pw``, ``bcrypt-pw``) as
  possible keys, and ``enabled``, ``legacy``, or ``disabled`` as possible values.
  Enabled means the hash is enabled for all cases. Disabled
  means IRRd treats the hash as if it is unknown, rejecting authentication and
  rejecting ``auth`` attributes using this hasher in new or updated authoritative
  `mntner` objects. Legacy is in between: authentication with existing hashes is
  permitted, ``auth`` attributes in new or modified authoritative objects
  are not.
  |br| **Default**: ``enabled`` for ``md5-pw`` and ``bcrypt-pw``,
  ``legacy`` for ``crypt-pw``
  |br| **Change takes effect**: upon the next update attempt.
* ``auth.authenticate_parents_route_creation``: whether to check for
  :ref:`related object maintainers <auth-related-mntners-route>` when users create
  new `route(6)` objects.
  |br| **Default**: true, check enabled
  |br| **Change takes effect**: upon the next update attempt.

.. danger::

    IRRd loads keys into the gnupg keyring when `key-cert` objects are
    imported. Their presence in the keyring is then used to validate requested
    changes. Therefore, the keyring referred to by ``auth.gnupg_keyring`` can
    not be simply reset, or PGP authentications may fail.
    However, you can use the ``irrd_load_pgp_keys`` command to refill the keyring
    in ``auth.gnupg_keyring``.

.. _limits: https://limits.readthedocs.io/en/latest/index.html

.. _conf-auth-set-creation:

auth.set_creation
"""""""""""""""""
The ``auth.set_creation`` setting configures the requirements when creating new
RPSL set objects. These are `as-set`, `filter-set`, `peering-set`, `route-set`
and `rtr-set`. It is highly customisable, but therefore also more complex
than most other settings.

There are two underlying settings:

* ``prefix_required`` configures whether an ASN prefix is required in the name
  of a set object. When enabled ``AS-EXAMPLE`` is invalid, while
  ``AS65537:AS-EXAMPLE`` or ``AS65537:AS-EXAMPLE:AS-CUSTOMERS``
  are valid.
* ``autnum_authentication`` controls whether the user also needs to pass
  authentication for the `aut-num` corresponding to the AS number used as the set
  name prefix. For example, if the set name is ``AS65537:AS-EXAMPLE:AS-CUSTOMERS``,
  this setting may require the creation to also pass authentication for the
  `aut-num` AS65537.
  The options are ``disabled``, ``opportunistic`` or ``required``.
  When disabled, this check is skipped. For opportunistic, the check is used, but
  passes if the aut-num does not exist. For required, the check is used and fails
  if the aut-num does not exist.
  
Note that even when ``autnum_authentication`` is set to ``required``,
if at the same time ``prefix_required`` is set to false, a set can be created
without a prefix or with one, per ``prefix_required``.
But if it has a prefix, there *must* be a corresponding
aut-num object for which authentication *must* pass, per ``autnum_authentication``.

You can configure one common for all set classes under the key ``COMMON``,
and/or specific settings for specific classes using the class name as key.
An example::

    irrd:
      auth:
          set_creation:
              COMMON:
                  prefix_required: true
                  autnum_authentication: required
              as-set:
                  prefix_required: true
                  autnum_authentication: opportunistic
              rtr-set:
                  prefix_required: false
                  autnum_authentication: disabled

This example means:

* New `as-set` objects must include an ASN prefix in their name
  and the user must pass authentication for the corresponding `aut-num` object,
  if it exists. If the `aut-num` does not exist, the check passes.
* New ``rtr-set`` objects are not required to include an ASN prefix in their
  name, but this is permitted. The user never has to pass authentication for
  the corresponding `aut-num` object, regardless of whether it exists.
* All other new set objects must include an ASN prefix in their name, an `aut-num`
  corresponding that AS number must exist, and the user must pass authentication
  for that `aut-num` object.

All checks are only applied when users create new set objects in authoritative
databases. Authoritative updates to existing objects, deletions, or objects from
mirrors are never affected. When looking for corresponding `aut-num` objects,
IRRd only looks in the same IRR source.

**Default**: ``prefix_required`` is enabled, ``autnum_authentication``
set to ``opportunistic`` for all sets. Note that settings under the
``COMMON`` key override these IRRd defaults, and settings under set-specific
keys in turn override settings under the ``COMMON`` key.
|br| **Change takes effect**: upon the next update attempt.


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
* ``rpki.roa_source``: a URL to a JSON file with ROA exports, in the format
  as produced by the RIPE NCC RPKI validator or rpki-client with the
  ``-j`` flag. When set, this enables the
  :doc:`RPKI-aware mode </admins/rpki>`. To disable RPKI-aware mode,
  set this to ``null``.
  Supports HTTP(s), FTP or local file URLs.
  |br| **Default**: ``https://rpki.gin.ntt.net/api/export.json``
  |br| **Change takes effect**: after SIGHUP. The first RPKI ROA import may
  take several minutes, after which RPKI-aware mode is enabled.
* ``rpki.roa_import_timer``: the time in seconds between two attempts to import
  the ROA file from ``roa_source`` and update the RPKI status of all
  qualifying route(6) objects.
  |br| **Default**: ``3600``.
  |br| **Change takes effect**: after SIGHUP.
* ``rpki.slurm_source``: a URL to a SLURM (`RFC8416`_) file. When set, the
  ``prefixAssertions`` and ``prefixFilters`` entries in the SLURM file
  are used to filter/amend the data from ``roa_source``.
  See the :ref:`SLURM documentation <rpki-slurm>` for more details.
  Supports HTTP(s), FTP or local file URLs.
  |br| **Default**: undefined, optional
  |br| **Change takes effect**: after SIGHUP, upon next full ROA import.
* ``rpki.pseudo_irr_remarks``: the contents of the remarks field for pseudo-IRR
  objects created for each ROA. This can have multiple lines. ``{asn}`` and
  ``{prefix}`` are replaced with the ROA's AS number and prefix, respectively.
  When adding this to the configuration, use the `|` style to preserve newlines, as
  shown in the example configuration file above.
  |br| **Default**::
  |br| `This AS{asn} route object represents routing data retrieved`
  |br| `from the RPKI. This route object is the result of an automated`
  |br| `RPKI-to-IRR conversion process performed by IRRd.`
  |br| **Change takes effect**: after the next ROA import.
* ``rpki.notify_invalid_enabled``: whether to send notifications to contacts
  of route(6) objects newly marked RPKI invalid in authoritative sources.
  Set to ``true`` or ``false``. This setting is required if ``rpki.roa_source``
  is set and one or more authoritative sources are configured.
  It is recommended to carefully read the
  :ref:`RPKI notification documentation <rpki-notifications>`, as this may
  sent out notifications to many users.
  **DANGER: care is required with this setting in testing setups**
  **with live data, as it may send bulk emails to real resource contacts, unless**
  **``email.recipient_override`` is also set.**
  |br| **Default**: undefined
  |br| **Change takes effect**: the next time an authoritative route(6)
  object is newly marked RPKI invalid.
* ``rpki.notify_invalid_subject``: the subject of the email noted
  in ``notify_invalid_enabled``.
  The string ``{sources_str}`` will be replaced with the name
  of the source(s) (e.g. ``NTTCOM``) of the relevant objects, and
  {object_count} with the number of objects listed in the email.
  |br| **Default**: ``route(6) objects in {sources_str} marked RPKI invalid``
  |br| **Change takes effect**: after the next ROA import.
* ``rpki.notify_invalid_header``: the header of the email noted in
  ``notify_invalid_enabled``.
  The string ``{sources_str}`` will be replaced with the name
  of the source(s) (e.g. ``NTTCOM``) of the relevant objects, and
  ``{object_count}`` with the number of objects listed in the email. When adding
  this to the configuration, use the `|` style to preserve newlines, as
  shown in the example configuration file above.
  In the notification emails, this is only followed by a list of newly invalid
  objects, so this header should explain why this email is being sent and
  what the list of objects is about.
  |br| **Default**:
  |br| `This is to notify that {object_count} route(6) objects for which you are a`
  |br| `contact have been marked as RPKI invalid. This concerns`
  |br| `objects in the {sources_str} database.`
  |br|
  |br| `You have received this message because your e-mail address is`
  |br| `listed in one or more of the tech-c or admin-c contacts, on`
  |br| `the maintainer(s) for these route objects.`
  |br|
  |br| `The {object_count} route(6) objects listed below have been validated using`
  |br| `RPKI origin validation, and found to be invalid. This means that`
  |br| `these objects are no longer visible on the IRRd instance that`
  |br| `sent this e-mail.`
  |br|
  |br| `This may affect routing filters based on queries to this IRRd`
  |br| `instance. It is also no longer possible to modify these objects.`
  |br|
  |br| `To resolve this situation, create or modify ROA objects that`
  |br| `result in these route(6) being valid, or not_found. If this`
  |br| `happens, the route(6) objects will return to being visible.`
  |br| `You may also delete these objects if they are no longer`
  |br| `relevant.`
  |br| **Change takes effect**: after the next ROA import.


Scope filter
~~~~~~~~~~~~
* ``scopefilter.prefixes``: a list of IPv4 or IPv6 prefixes which are
  considered out of scope. For details, see the
  :doc:`scope filter documentation </admins/scopefilter>`.
  |br| **Default**: none, prefix scope filter validation not enabled.
  |br| **Change takes effect**: after SIGHUP. Updating the status of
  existing objects may take 10-15 minutes.
* ``scopefilter.asns``: a list of ASNs which are considered out of
  scope. Ranges are also permitted, e.g. ``64496-64511``.
  For details, see the
  :doc:`scope filter documentation </admins/scopefilter>`.
  May contain plain AS number, or a range, e.g. ``64496-64511``.
  |br| **Default**: none, ASN scope filter validation not enabled.
  |br| **Change takes effect**: after SIGHUP. Updating the status of
  existing objects may take 10-15 minutes.

Route object preference
~~~~~~~~~~~~~~~~~~~~~~~
* ``route_object_preference.update_timer``: the time in seconds between
  full updates of the
  :doc:`route object preference </admins/route-object-preference>` status
  for all objects in the database. Note that the status is already updated
  on changes to objects as they are processed - this periodic process sets
  the initial state and resolver small inconsistencies. This setting
  has no effect unless at least one source has
  ``sources.{name}.route_object_preference`` set.
  |br| **Default**: 3600 (1 hour)
  |br| **Change takes effect**: after SIGHUP.

In addition to this, the route object preference of each source can be set
in ``sources.{name}.route_object_preference``, documented below.

Sources
~~~~~~~
* ``sources_default``: a list of sources that are enabled by default, or when a
  user selects all sources with ``-a``. The order of this list defines the
  search priority as well. It is not required to include all known sources in
  the default selection. If ``rpki.roa_source`` is defined, this may also
  include ``RPKI``, which contains pseudo-IRR objects generated from ROAs.
  |br| **Default**: not defined. All sources are enabled, but results are not
  ordered by source.
  |br| **Change takes effect**: after SIGHUP, for all subsequent queries.
* ``sources.{name}``: settings for a particular source. The name must be
  all-uppercase, start with a letter, and end with a letter or digit. Valid
  characters are letters, digits and dashes. The minimum length is two
  characters. If ``rpki.roa_source`` is defined, ``RPKI`` is a reserved
  source name, as it contains pseudo-IRR objects generated from ROAs.
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
* ``sources.{name}.export_destination_unfiltered``: a path to save full exports,
  including a serial file, of this source. This is identical to
  ``export_destination``, except that the files saved here contain full unfiltered
  password hashes from mntner objects.
  Sharing password hashes externally is a security risk, the unfiltered data
  is intended only to support
  :doc:`availability and data migration </admins/availability-and-migration>`.
  **This setting is deprecated and will be removed in IRRD 4.5.**
  |br| **Default**: not defined, no exports made.
  |br| **Change takes effect**: after SIGHUP, at the next ``export_timer``.
* ``sources.{name}.export_timer``: the time between two full exports of all
  data for this source. The minimum effective time is 15 seconds, and this is
  also the granularity of the timer.
  |br| **Default**: ``3600``.
  |br| **Change takes effect**: after SIGHUP
* ``sources.{name}.nrtm_access_list``: a reference to an access list in the
  configuration, where only IPs in the access list are permitted filtered access
  to the NRTM stream for this particular source (``-g`` queries).
  Filtered means password hashes are not included.
  This same list is used to restrict access to
  :ref:`GraphQL journal queries <graphql-journal>`.
  |br| **Default**: not defined, all access denied except to clients in
  ``nrtm_access_list_unfiltered``.
  |br| **Change takes effect**: after SIGHUP, upon next request.
* ``sources.{name}.nrtm_access_list_unfiltered``: a reference to an access list
  in the configuration, where IPs in the access list are permitted unfiltered
  access to the NRTM stream for this particular source (``-g`` queries).
  Unfiltered means full password hashes are included.
  Sharing password hashes externally is a security risk, the unfiltered data
  is intended only to support
  :doc:`availability and data migration </admins/availability-and-migration>`.
  **This setting is deprecated and will be removed in IRRD 4.5.**
  |br| **Default**: not defined, all access denied. Clients in
  ``nrtm_access_list``, if defined, have filtered access.
  |br| **Change takes effect**: after SIGHUP, upon next request.
* ``sources.{name}.nrtm_query_serial_range_limit``: the maximum number of
  serials a client may request in one NRTM query, if otherwise permitted.
  This is intended to limit the maximum load of NRTM queries - it is checked
  before IRRd runs any heavy database queries. The limit is applied to the
  requested range regardless of any gaps, i.e. querying a range of ``10-20``
  is allowed if this setting to be at least 10, even if there are no entries
  for some of those serials. IRRd is aware of the serial ``LAST`` refers to
  and will take that into account.
  |br| **Default**: not defined, no limits on NRTM query size.
  |br| **Change takes effect**: after SIGHUP, upon next request.
* ``sources.{name}.strict_import_keycert_objects``: a setting used when
  migrating authoritative data that may contain `key-cert` objects.
  See the :doc:`data migration guide </admins/availability-and-migration>`
  for more information.
  See the :doc:`deployment guide </admins/deployment>` for more information.
  |br| **Default**: false
  |br| **Change takes effect**: after SIGHUP, upon next request.
* ``sources.{name}.rpki_excluded``: disable RPKI validation for this source.
  If set to ``true``, all objects will be considered not_found for their
  RPKI status.
  |br| **Default**: false, RPKI validation enabled.
  |br| **Change takes effect**: after SIGHUP, upon next full ROA import.
* ``sources.{name}.scopefilter_excluded``: disable scope filter validation for
  this source. If set to ``true``, all objects will be considered in scope
  for their scope filter status.
  |br| **Default**: false, scope filter validation enabled.
  |br| **Change takes effect**: after SIGHUP, within a few minutes.
* ``sources.{name}.route_object_preference``: the
  :doc:`route object preference </admins/route-object-preference>` for
  this source. Higher number is a higher preference.
  |br| **Default**: unset, not considered for route object preference.
  |br| **Change takes effect**: after SIGHUP, after next periodic update.
* ``sources.{name}.suspension_enabled``: a boolean for whether this source
  allows :doc:`suspension and reactivation of objects </admins/suspension>`.
  Can only be enabled if `authoritative` is enabled.
  |br| **Default**: ``false``.
  |br| **Change takes effect**: after SIGHUP, for all subsequent changes.


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
  |br| **Default**: not defined.
  |br| **Change takes effect**: after full IRRd restart.
* ``log.level``: the loglevel, one of `DEBUG`, `INFO`, `WARNING`, `ERROR`,
  `CRITICAL`. The recommended level is `INFO`.
  |br| **Default**: ``INFO``.
  |br| **Change takes effect**: after SIGHUP.

IRRd requires ``logfile_path`` or ``logging_config_path`` to be set if
IRRd is started into the background. If IRRd is started with ``--foreground``,
these options may be left undefined and all logs will be printed to stdout.

If you need more granularity than these settings, you can set
``log.logging_config_path``. This allows you to set custom Python logging
configuration This can not be used together with ``log.logfile_path``
or ``log.level`` - the configuration you provide will be the only logging
configuration.

.. note::
    An incorrect configuration may cause log messages
    to be lost. The ``log.logging_config_path`` setting is powerful,
    but also allows more mistakes.

The ``log.logging_config_path`` setting should point to a path of a Python
file, from which a dictionary named ``LOGGING`` will be imported,
which is then passed to the ``dictConfig()`` Python logging method.

.. highlight:: python
    :linenothreshold: 5

As a start, this is the internal ``LOGGING`` config used by IRRd when
the level is set to `DEBUG` and path to ``/var/log/irrd.log``::


    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s'
            },
        },
        'handlers': {
            # "File" handler which writes messages to a file.
            # Note that the "file" key is arbitrary, you can
            # create ones like "file1", "file2", if you want
            # multiple handlers for different paths.
            'file': {
                'class': 'logging.handlers.WatchedFileHandler',
                'filename': '/var/log/irrd.log',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            # Tune down some very loud and not very useful loggers
            # from libraries. Propagation is the default, which means
            # loggers discard messages below their level, and then the
            # remaining messages are passed on, eventually reaching
            # the actual IRRd logger.
            'passlib.registry': {
                'level': 'INFO',
            },
            'gnupg': {
                'level': 'INFO',
            },
            'sqlalchemy': {
                'level': 'WARNING',
            },
            # Actual IRRd logging feature, passing the log message
            # to the "file" handler defined above.
            '': {
                'handlers': ['file'],
                'level': 'DEBUG',
            },
        }
    }

If you place this in a Python file, and set ``log.logging_config_path``
to the path of that file, you have correctly configured custom logging.
For example, you could define a different logger for ``irrd.mirroring``
with a different handler, to send mirroring logs to another file,
and use the ``propagate`` property to not send them to your regular
log file, as in this example::

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '%(asctime)s irrd[%(process)d]: [%(name)s#%(levelname)s] %(message)s'
            },
        },
        'handlers': {
            'file-regular': {
                'class': 'logging.handlers.WatchedFileHandler',
                'filename': '/var/log/irrd.log',
                'formatter': 'verbose',
            },
            'file-mirroring': {
                'class': 'logging.handlers.WatchedFileHandler',
                'filename': '/var/log/irrd-mirroring.log',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'passlib.registry': {
                'level': 'INFO',
            },
            'gnupg': {
                'level': 'INFO',
            },
            'sqlalchemy': {
                'level': 'WARNING',
            },
            'irrd.mirroring': {
                'handlers': ['file-mirroring'],
                'level': 'DEBUG',
                # propagate=False means the handling will stop
                # here, i.e. not be passed to loggers below this
                # one, for any matching log messages
                'propagate': False,
            },
            '': {
                'handlers': ['file-regular'],
                'level': 'DEBUG',
            },
        }
    }


Also see the `Python documentation for logging`_ or
`this example from the logging cookbook`_.

Changes to ``log.logging_config_path`` take effect after a full IRRd restart.
Errors in the logging config may prevent IRRd from starting. Any such errors
will be printed to the console.

.. _Python documentation for logging: https://docs.python.org/3/library/logging.config.html#logging-config-dictschema
.. _this example from the logging cookbook: https://docs.python.org/3/howto/logging-cookbook.html#an-example-dictionary-based-configuration

Compatibility
~~~~~~~~~~~~~
* ``compatibility.inetnum_search_disabled``: enabling this setting is
  recommended when the IRRd instance never processes `inetnum` objects.
  It enables :ref:`high performance prefix queries <performance_prefix_queries>`
  for all queries. However, if this is enabled and your IRRd instance does
  store `inetnum` objects, they may be missing from responses to queries.
  Therefore, only enable this when you do not process any `inetnum` objects.
  |br| **Default**: ``false``, i.e. `inetnum` search is enabled.
  |br| **Change takes effect**: after SIGHUP, for all subsequent queries.
* ``compatibility.ipv4_only_route_set_members``: if set to ``true``, ``!i``
  queries will not return IPv6 prefixes. This option can be used for limited
  compatibility with IRRd version 2. Enabling this setting may have a
  performance impact on very large responses.
  |br| **Default**: ``false``, IPv6 members included.
  |br| **Change takes effect**: after SIGHUP, for all subsequent queries.

.. _RFC8416: https://tools.ietf.org/html/rfc8416
