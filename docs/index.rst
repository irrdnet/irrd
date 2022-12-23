IRRd version |version|
======================

Internet Routing Registry daemon version 4 is an IRR database server,
processing IRR objects in the RPSL format.
Its main features are:

* Validating, cleaning and storing IRR data, and extracting
  information for indexing.
* Providing several query interfaces to query the IRR data.
* Handling authoritative IRR data, and allowing users with the appropriate
  authorisation to submit requests to change objects.
* Mirroring other IRR databases using file imports and NRTM.
* Offering NRTM mirroring and full export services to other databases.

This IRRd version 4 project was originally commissioned in 2018 by NTT_ and
designed and developed by `Reliably Coded`_ (known as DashCare until 2021).
Since then, `Reliably Coded`_ has been maintaining and extending IRRd significantly,
for, or with support of, NTT_, ARIN_, Merit_, `RIPE NCC Community Projects Fund`_,
LACNIC_, Netnod_ and Internetstiftelsen_. This has taken place in the form of
development contracts, support contracts, or grants.

`Older versions`_ of IRRd are or were in use at by various IRR operators.
places. Difficulties with continued maintenance and extension of these
older versions lead to the IRRd v4 project.

.. _NTT: https://www.gin.ntt.net
.. _Reliably Coded: https://www.reliablycoded.nl
.. _ARIN: https://www.arin.net/
.. _Merit: https://www.radb.net/
.. _RIPE NCC Community Projects Fund: https://www.ripe.net/support/cpf
.. _LACNIC: https://www.lacnic.net/
.. _Netnod: https://www.netnod.se/
.. _Internetstiftelsen: https://internetstiftelsen.se/
.. _Older versions: https://github.com/irrdnet/irrd-legacy

.. warning::
    IRRd 4.2.x versions prior to 4.2.3 had a security issue that exposed password
    hashes in some cases. All 4.2.x users are urged to
    update to 4.2.3 or later.
    See the :doc:`4.2.3 release notes </releases/4.2.3>` for further details.

For administrators
------------------

This documentation is mainly for administrators of IRRd deployments.

.. toctree::
   :caption: For administrators
   :maxdepth: 1

   admins/deployment
   admins/configuration
   admins/availability-and-migration
   admins/migrating-legacy-irrd
   admins/status_page
   admins/faq


.. toctree::
   :caption: Validation, suppression and suspension
   :maxdepth: 1

   admins/object-validation
   admins/object-suppression
   admins/rpki
   admins/scopefilter
   admins/route-object-preference
   admins/suspension

Running queries
---------------

.. toctree::
   :caption: Running queries
   :maxdepth: 1

   users/queries/index
   users/queries/graphql
   users/queries/whois
   users/queries/event-stream

For end users
-------------

This documentation is mainly for end users, who are performing queries on IRRd
instances, or trying to add objects to an instance, or running mirrors of
an IRRd instance.

.. toctree::
   :caption: For end users
   :maxdepth: 1

   users/database-changes
   users/mirroring

For developers
--------------

This documentation is mainly for people who want to develop on the IRRd code base
itself, or want to know how it works.

.. toctree::
   :caption: For developers
   :maxdepth: 1

   development/architecture
   development/development-setup
   development/storage

Other
-----
.. toctree::
   :caption: Other
   :maxdepth: 1

   releases/index.rst
   security
   license
