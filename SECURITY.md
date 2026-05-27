# Security Policy

## Supported Versions

This is a learning-oriented lab series. Only the latest tagged release is
actively maintained; earlier tags are kept for historical reference but will
not receive security updates.

| Version | Supported |
| ------- | --------- |
| Latest release (`main`) | Yes |
| Older tags | No |

## Reporting a Vulnerability

If you discover a security issue in any lab - a leaked credential pattern,
unsafe default in a Bicep template, an injection risk in a notebook, etc. -
**please do not open a public issue.**

Instead, report it privately via GitHub's
[security advisories](https://github.com/corticalstack/awesome-foundry-nextgen/security/advisories/new)
so it can be triaged before public disclosure.

When reporting, please include:

- The lab number / file path where the issue lives
- A short description of the impact
- Steps to reproduce (or a proof of concept)
- Any suggested mitigation

You can expect an initial acknowledgement within 7 days.

## Out of scope

- Issues in upstream Azure services (report to
  [Microsoft Security Response Center](https://msrc.microsoft.com/) instead)
- Issues in third-party Python packages pinned in `pyproject.toml` (report
  upstream to the package maintainers)
- Findings against deployments you have provisioned yourself using the Bicep
  templates - these are your own resources to harden
