Internet Routing Registry Daemon (IRRd) Version 4
=================================================

.. image:: https://circleci.com/gh/irrdnet/irrd4.svg?style=svg
     :target: https://circleci.com/gh/irrdnet/irrd4

.. image:: https://coveralls.io/repos/github/irrdnet/irrd4/badge.svg?branch=master
     :target: https://coveralls.io/github/irrdnet/irrd4?branch=master

.. image:: https://readthedocs.org/projects/irrd4/badge/?version=latest
     :target: http://irrd4.readthedocs.io/en/latest/?badge=latest

.. image:: https://pyup.io/repos/github/irrdnet/irrd4/shield.svg
     :target: https://pyup.io/repos/github/irrdnet/irrd4/

------------

NTT_ has tasked DashCare_ to develop
a new version of the Internet Routing Registry Daemon (IRRDv4). This is an IRR
database server, its main features being storing IRR data in RPSL format,
mirroring other IRR services and answering queries of varying complexity.

The v2 and v3 versions of IRRd are currently in use at NTT and RADB, amongst
other places. The development process of IRRd up to version 3 has led to a
project using many different architectures, styles and languages. The
`current v3 project`_ is near impossible to maintain,
test and extend. Many of its design choices have been made in a distant past,
and are no longer the best choice for today.

This project will address these issues by developing an entirely new version of
IRRD, featuring:

* A single architecture design that encompasses all current features and
  provides room for extensibility in the future, to support new standards or
  add other functionality at relatively low cost.
* A single codebase that is well documented, maintainable and consistent in
  style and approach.
* A comprehensive suite of both unit and integration tests to ensure the
  continued correctness of IRRD.
* Extensive compatibility with existing data submission, RPSL queries and
  mirroring sources, to ease upgrades to IRRDv4.
* A proxy module which can be used to compare the results of an existing
  IRRD deployment to a new IRRDv4 deployment to assure the correct and
  consistent functioning, making upgrades from previous versions very low risk.

.. _NTT: https://us.ntt.net
.. _DashCare: https://www.dashcare.nl
.. _current v3 project: https://github.com/irrdnet/irrd
