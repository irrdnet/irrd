Web interface and internal authentication
=========================================

Along with HTTP based API calls, GraphQL and the status page, IRRD contains
a web interface that allows users to migrate their authoritative maintainers
to an IRRD internal authentication method. It also offers more secure
alternatives to email submissions and override access.

The web interface contains a RPSL submission form, accepting
the same format as emails, to make object changes. This form accepts
the new internal authentication as well as passwords, and is meant
as a more practical and more secure alternative to emails.

The submission form and internal authentication only affect
objects in authoritative sources.

IRRD internal authentication
----------------------------
Traditional maintainer objects authenticate with a list of passwords
and/or PGP keys in the maintainer object. In IRRD internal authentication,
the permissions are kept in a separate storage, i.e. not in RPSL
objects. The major features of internal over traditional are:

* Users can choose whether to give other users access to change
  permissions on the maintainer, or only modify other objects.
  In traditional authentication, anyone with maintainer access can
  essentially take over the maintainer.
* Users can create API keys with limited permissions, rather than include
  a password (that allows a full take-over) in emails.
  API keys are also random, where user passwords are often easier to guess.
* Users can submit object updates after logging in, without needing
  to pass further authentication.
* Internal authentication can be combined with traditional, but
  this is not recommended.
* Logins on the web interface can be protected with two-factor
  authentication.
* Hashes of (new) user passwords are no longer part of RPSL objects.
* Users with user management permission can see a log of actions
  taken on their objects or maintainer, and who performed these actions.
  This log includes changes made through any submission method.
* User passwords can not be used directly for authentication of
  e.g. email updates.

You can allow migrations with the
``auth.irrd_internal_migration_enabled`` setting.
By default, this is disabled.
Even with migration disabled, users can use the object submission
interface to submit in the same format as email, by including the
``password`` or ``override`` pseudo-attributes.

Override access
---------------
Independent of whether regular users can migrate their account
(``auth.irrd_internal_migration_enabled``), you can
use the web interface to provide override access.
Rather than sharing a single password with your staff with traditional
override access, you can use this feature to restrict override access
to HTTPS and two-factor authenticated users.

To enable override access for a user, the user must first create
an account and set up two-factor authentication.
Then, use the ``irrdctl user-change-override`` command
to enable or disable access for the user.

User registration
-----------------
Users can register their own account through the interface, after verifying
their e-mail address. Users can also independently change their details or
request a link to reset. Two-factor authentication is
supported with WebAuthn tokens (SoloKeys, YubiKey, PassKey, etc.) or
one time password (TOTP, through Google Authenticator, Authy, etc.)

Significant changes and authentication failures are logged in IRRD's log file,
and a notification is mailed to the user.
Important endpoints (e.g. login attempts) have rate limiting.

If a user loses access to all their two-factor authentication methods,
an IRRD operator needs to reset this for them. You can do this with
the ``irrdctl user-mfa-clear`` command.

Maintainer migration
--------------------
Migrating a maintainer can be done by any registered user when
``auth.irrd_internal_migration_enabled`` is enabled, and involves
the following steps:

* The user requests migration with the maintainer name and one of the
  current valid passwords on the maintainer.
* IRRD will mail all `admin-c` contacts on the maintainer with the
  confirmation link (all will receive the same link).
* The same user must open the confirmation link, and confirm again with
  a current valid password.
* The maintainer is now migrated. Existing methods are kept.

A migrated maintainer must have ``IRRD-INTERNAL-AUTH`` as one of
the ``auth`` methods. This is added as part of the migration process.

API tokens
----------
All linked users can add API tokens for a maintainer. Tokens can have
a restriction on submission methods or IP ranges. Each token has a
secret, that can be passed in ``api_keys`` in an HTTP call,
or the pseudo-attribute ``api-key`` in email submissions.
API keys can not be used to update their own maintainer.
