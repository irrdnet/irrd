# Internet Routing Registry Daemon (IRRd) Version 4

[NTT](https://us.ntt.net) has tasked [DashCare](https://dashcare.nl) to develop
a new version of the Internet Routing Registry Daemon (IRRDv4). This is an IRR
database server, its main features being storing IRR data in RPSL format,
mirroring other IRR services and answering queries of varying complexity.

Current versions of IRRDv2 IRRDv3 are currently in use at NTT and RADB, amongst
other places. The development process of IRRD up to version 3 has led to a
project using many different architectures, styles and languages. The current
v3 project is near impossible to maintain, test and extend. Many of its design
choices have been made in a distant past, and are no longer the best choice for
today.

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
