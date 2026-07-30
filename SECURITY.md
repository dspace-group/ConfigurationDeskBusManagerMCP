# Security Policy

## Supported Versions

This project is in active development. Security fixes are applied to the latest released version on the `main` branch. Older versions are not maintained.

| Version | Supported |
| --- | --- |
| latest (`main`) | :white_check_mark: |
| older releases | :x: |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, use one of the following private channels:

1. **GitHub Private Vulnerability Reporting** — open the repository's **Security → Report a vulnerability** tab (preferred).
2. **Email** — contact the maintainer at `ARamananda-Rao@dspace.hr`.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, or a proof of concept.
- Affected version(s) and relevant environment details.

You can expect an initial acknowledgement within a few business days. We will keep you informed as we investigate and work on a fix, and will credit you in the release notes unless you prefer to remain anonymous.

## Scope

This server automates a locally installed dSPACE ConfigurationDesk via COM and uses local `stdio` as its supported public transport. Streamable HTTP is disabled by default and restricted to loopback hosts when explicitly enabled. LAN, remote, and public HTTP deployments are unsupported in this release.