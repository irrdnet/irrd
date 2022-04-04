Security Policy
===============

Reporting a Vulnerability
-------------------------

If you have found an issue, strange behaviour, possible oversight,
or anything else that may have security implications, please do not
report it in the GitHub repository, but email irrd@reliablycoded.nl.

Supported Versions
------------------

The current main branch, latest minor version (currently 4.2.x) and one older 
minor version are always supported for security updates. Older versions
may be supported for longer in support contracts or specific agreements.

.. list-table::
   :header-rows: 1

   * - Version
     - Supported
   * - Main branch
     - Yes
   * - 4.2.x
     - Yes
   * - 4.1.x
     - Yes
   * - 4.0.x
     - No

Versions older than 4.0 are an
`entirely different project <https://github.com/irrdnet/irrd-legacy/>`_.

Security process and disclosure
-------------------------------

* Upon receiving a notification of a possible security issue,
  the maintainers will investigate the issue to determine whether
  there is an impact and what kind of impact.
* The reporter will receive this initial assessment within one week,
  but generally sooner.
* If the issue has a security impact, the maintainers will implement
  as resolution as soon as reasonable. The time frame for this depends
  on the complexity, but will usually be in the order of
  a few days to a few weeks.
* Once a fix for the issue is ready, parties on the advance notification
  list will be provided with details, patches and pre-release packages.
* One week later, the details will be publicly released
  along with new IRRd releases.
* Reporters will be credited if desired.
* This timeline may be accelerated or modified if details are published
  prematurely, or if further discussion or coordination with other parties
  is needed.

Advance notification list
-------------------------

The advance notification list is a list of operators of registries of such
size or importance that security issues may have significant operational
impact, and operators with a support contract with Reliably Coded.

The list is not public. If you believe you should be on this list,
contact the address listed above.

Security issues in IRRd deployments
-----------------------------------

The maintainers do not run production deployments of IRRd. For issues
with particular instances, rather than the IRRd software, contact
the security contact of the respective IRRd operator.

Best effort
-----------

Note that, like all IRRd maintenance, this process is best effort, except
where otherwise agreed in a separate support contract.
The existence of this policy does not negate the disclaimers regarding warranty,
liability etc., in the IRRd
`license <https://github.com/irrdnet/irrd/blob/main/LICENSE>`_.
