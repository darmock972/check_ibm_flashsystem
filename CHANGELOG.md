# Changelog

## 1.0.2-secure

- Changed Nagios text output to use one perfdata separator only.
- Improved Nagios GUI status visibility by keeping health summary before the perfdata separator.
- Added `--version` option.
- Added REST API User-Agent header.
- Shortened default firmware display to the code level; full build remains available in verbose output.

## 1.0.1-secure

- Removed command-line password option.
- Sanitized README and example Nagios configuration files.
- Removed environment-specific hostnames, IP addresses, usernames, and sample secrets.
- Kept only secure credential methods: `--password-file` and `--password-env`.
- Removed generated Python cache files from the release package.

## 1.0.0

- Initial Nagios Core plugin for IBM FlashSystem / Storage Virtualize REST API.
- Added checks for nodes, drives, pools, enclosures, PSUs, and batteries.
