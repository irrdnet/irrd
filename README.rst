Internet Routing Registry Daemon (IRRd) Version 4
=================================================

.. image:: https://circleci.com/gh/irrdnet/irrd.svg?style=svg
     :target: https://circleci.com/gh/irrdnet/irrd

.. image:: https://readthedocs.org/projects/irrd/badge/?version=stable
     :target: http://irrd.readthedocs.io/en/stable/?badge=stable

.. image:: https://pyup.io/repos/github/irrdnet/irrd/shield.svg
     :target: https://pyup.io/repos/github/irrdnet/irrd/

------------

.. image:: https://irrd.readthedocs.io/en/latest/_static/logo.png
     :alt: IRRd logo. Copyright (c) 2019, Natasha Allegri

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

`Older versions`_ of IRRd are or were in use at NTT and RADB, amongst other
places. Difficulties with continued maintenance and extension of these
older versions lead to the IRRd v4 project.

This project was originally commissioned by NTT_ and designed and
developed by DashCare_.

Please see the documentation_ for more.

.. _NTT: https://www.gin.ntt.net
.. _DashCare: https://www.dashcare.nl
.. _Older versions: https://github.com/irrdnet/irrd-legacy
.. _documentation: http://irrd.readthedocs.io/en/stable/
