# Governance

## Responsibility

- **Main responsible person:** Akshay Ramananda Rao ([@Akshay-r-rao](https://github.com/Akshay-r-rao))
- **Deputy:** Ivan Maras ([@imdshr](https://github.com/imdshr))

The main responsible person owns repository content, maintenance, and release
decisions. The deputy assumes responsibility when the main responsible person
is unavailable. Any ownership change must update this document and
[CODEOWNERS](.github/CODEOWNERS) in the same reviewed pull request.

## Contributors

Only approved dSPACE employees receive direct repository access. External
contributors use forks and pull requests.

## Reviews

- Pull requests must be reviewed before merge.
- Changes to release, security, licensing, package metadata, and executable
  packaging must be reviewed from the main responsible person or deputy.
- `main` remains protected by the required CI and Code Owners review.

## Releases

- Releases use semantic version tags in the form `vMAJOR.MINOR.PATCH`.
- The tag version must match both package manifests and the executable version.
- Release artifacts are built by GitHub Actions and include a checksum and
  third-party notices.
- Direct release creation outside the release workflow is not permitted.

## Security

Security reports follow [SECURITY.md](SECURITY.md). Do not report security
vulnerabilities through public issues.