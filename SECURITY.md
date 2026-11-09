# Security Policy

## Reporting a Vulnerability

If you have found an issue, strange behaviour, possible oversight,
or anything else that may have security implications, please do not
report it in the GitHub repository:

- email irrd@reliablycoded.nl, or
- file it as a [GitHub Security Advisory](https://github.com/irrdnet/irrd/security/advisories/new).

Do not create a GitHub issue or pull request.
If you have a patch, you can attach it to the email or the security advisory.

## Supported Versions

The current main branch, latest minor version and one older
minor version are always supported for security updates. Older versions
may be supported for longer in support contracts or specific agreements.

| Version | Supported |
| --- | --- |
| Main branch | Yes |
| 4.5.x | Yes |
| 4.4.x | Yes |
| 4.3.x | No |
| 4.2.x | No |
| 4.1.x | No |
| 4.0.x | No |

Versions older than 4.0 are an
[entirely different project](https://github.com/irrdnet/irrd-legacy/).

## Security process and disclosure

- Upon receiving a notification of a possible security issue,
  we will investigate the issue to determine whether
  there is an impact and what kind of impact.
- The reporter will receive this initial assessment within one week,
  but generally sooner.
- If the issue has a security impact, we will implement
  a resolution as soon as reasonable. The time frame for this depends
  on the complexity, but will usually be in the order of
  a few days to a few weeks.
- Once a fix for the issue is ready, we will assess whether a
  coordinated deployment plan is warranted. In that case, external stakeholders
  may receive details before the public release.
- Reporters will be credited if desired. Please let us know how to credit you.
  If you prefer to remain anonymous, this is also possible.
- If the issue was filed through a GitHub Security Advisory, we will edit
  the advisory text you originally submitted.

## Security issues in IRRD deployments

We do not run production deployments of IRRD. For issues
with particular instances, rather than the IRRD software, contact
the security contact of the respective IRRD operator.

## Scope of availability issues

IRRD's whois and HTTP services are open to the public by design, and
deployments are encouraged to apply network level protections against
high traffic volumes, as covered in the
[deployment documentation](https://irrd.readthedocs.io/en/stable/admins/deployment/).
Reports of resource exhaustion are treated as security issues when they
involve amplification, where a small request forces disproportionate
work on the server, or persistence, where the impact remains after the
abusive traffic stops. Resource exhaustion purely from traffic volume,
which network level measures can mitigate, is treated as hardening.

## Best effort

Note that, like all IRRD maintenance, this process is best effort, except
where otherwise agreed in a separate support contract.
The existence of this policy does not negate the disclaimers regarding warranty,
liability etc., in the IRRD
[license](https://github.com/irrdnet/irrd/blob/main/LICENSE).
