Internet Routing Registry Daemon (IRRd) Version 4
=================================================

.. image:: https://circleci.com/gh/irrdnet/irrd.svg?style=svg
     :target: https://circleci.com/gh/irrdnet/irrd

.. image:: https://readthedocs.org/projects/irrd/badge/?version=stable
     :target: http://irrd.readthedocs.io/en/stable/?badge=stable

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

This IRRd version 4 project was originally commissioned in 2018 by NTT_ and
designed and developed by `Reliably Coded`_ (known as DashCare until 2021).
Since then, `Reliably Coded`_ has been maintaining and extending IRRd significantly,
for, or with support of, NTT_, ARIN_, Merit_, `RIPE NCC Community Projects Fund`_,
LACNIC_, Netnod_ and Internetstiftelsen_. This has taken place in the form of
development contracts, support contracts, or grants.

`Older versions`_ of IRRd are or were in use by various IRR operators.
Difficulties with continued maintenance and extension of these
older versions led to the IRRd v4 project.

Please see the extensive documentation_ for more on how to deploy and use IRRd.

.. _NTT: https://www.gin.ntt.net
.. _Reliably Coded: https://www.reliablycoded.nl
.. _ARIN: https://www.arin.net/
.. _Merit: https://www.radb.net/
.. _RIPE NCC Community Projects Fund: https://www.ripe.net/support/cpf
.. _LACNIC: https://www.lacnic.net/
.. _Netnod: https://www.netnod.se/
.. _Internetstiftelsen: https://internetstiftelsen.se/
.. _Older versions: https://github.com/irrdnet/irrd-legacy
.. _documentation: http://irrd.readthedocs.io/en/stable/
