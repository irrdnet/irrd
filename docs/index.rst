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

Legacy versions of IRRd are or were in use at NTT and RADB, amongst other
places. Difficulties with continued maintenance and extension of these
older versions lead to the IRRd v4 project.

This project was originally commissioned by NTT_ and designed and
developed by DashCare_.

.. _NTT: https://us.ntt.net
.. _DashCare: https://www.dashcare.nl

For administrators
------------------

This documentation is mainly for administrators of IRRd deployments.

.. toctree::
   :caption: For administrators
   :maxdepth: 1

   admins/deployment
   admins/configuration
   admins/migrating-legacy-irrd
   admins/object-validation
   admins/status_page
   admins/rpki
   admins/scopefilter

Running queries
---------------

.. toctree::
   :caption: Running queries
   :maxdepth: 1

   users/queries/index
   users/queries/graphql
   users/queries/whois

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
   license
