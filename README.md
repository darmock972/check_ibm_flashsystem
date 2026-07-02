![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/github/license/darmock972/check_ibm_flashsystem)
![GitHub release](https://img.shields.io/github/v/release/darmock972/check_ibm_flashsystem)

# check_ibm_flashsystem

A Nagios Core plugin for monitoring **IBM FlashSystem** and **IBM Storage Virtualize** systems using the native REST API.

The plugin performs hardware and storage health checks without requiring SNMP, and returns Nagios-compatible status codes and performance data.

---

## Features

- REST API monitoring
- Node canister health
- Drive health
- Storage pool monitoring
- Storage pool capacity thresholds
- Enclosure monitoring
- Power supply monitoring
- Battery monitoring
- Nagios performance data
- Secure password file authentication
- Python 3.8+

---

## Screenshot

Nagios Core monitoring an IBM FlashSystem.

![Nagios Screenshot](Screenshots/nagios_ok.png)

---

## Requirements

- Nagios Core
- Python 3.8 or newer
- Python `requests` module
- IBM FlashSystem / IBM Storage Virtualize with REST API enabled

Install the required Python module:

```bash
pip3 install requests
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/darmock972/check_ibm_flashsystem.git
cd check_ibm_flashsystem
```

Copy the plugin:

```bash
sudo cp check_ibm_flashsystem.py /usr/local/nagios/libexec/
sudo chmod +x /usr/local/nagios/libexec/check_ibm_flashsystem.py
```

---

# Creating a Monitoring User

For security reasons, **do not use the built-in `superuser` account** for monitoring.

Create a dedicated monitoring account with the minimum permissions required to read system status through the REST API.

The monitoring account should be able to read:

- System information
- Node canisters
- Drives
- Storage pools
- Enclosures
- Power supplies
- Batteries

The account should **not** have permissions to modify the storage system.

## Local Authentication

Create a local monitoring user from the FlashSystem GUI or CLI and assign it the appropriate **read-only** or **monitoring** role available in your Storage Virtualize version.

## LDAP / Active Directory

If your FlashSystem authenticates against LDAP or Active Directory, create a dedicated monitoring account and assign it the equivalent read-only role.

---

# Secure Password Storage

Store the password in a file readable only by the Nagios user.

```bash
sudo mkdir -p /etc/nagios/secrets

sudo nano /etc/nagios/secrets/flashsystem.pass

sudo chown nagios:nagios /etc/nagios/secrets/flashsystem.pass

sudo chmod 600 /etc/nagios/secrets/flashsystem.pass
```

The password file should contain **only the password**.

Example:

```text
MyVeryStrongPassword
```

---

# Testing the Plugin

Run the plugin manually before adding it to Nagios.

```bash
check_ibm_flashsystem.py \
    -H 192.168.1.100 \
    -u nagios \
    --password-file /etc/nagios/secrets/flashsystem.pass
```

Example output:

```text
OK - Claus-IBM: Nodes 2/2, Drives 12/12, PoolDR 67.8%, PSU 2/2, Batteries 2/2, FW 9.1.0.4
```

---

# Nagios Configuration

## commands.cfg

```cfg
define command{
    command_name    check_ibm_flashsystem
    command_line    $USER1$/check_ibm_flashsystem.py \
                    -H $HOSTADDRESS$ \
                    -u $ARG1$ \
                    --password-file $ARG2$
}
```

---

## hosts.cfg

```cfg
define host{
    use         linux-server
    host_name   IBM-FS01
    alias       IBM FlashSystem
    address     192.168.1.100
}
```

---

## services.cfg

```cfg
define service{
    use                     generic-service
    host_name               IBM-FS01
    service_description     IBM FlashSystem Health
    check_command           check_ibm_flashsystem!nagios!/etc/nagios/secrets/flashsystem.pass
}
```

---

# Example Output

```text
OK - Claus-IBM: Nodes 2/2, Drives 12/12, PoolDR 67.8%, PSU 2/2, Batteries 2/2, FW 9.1.0.4 | nodes_ok=2 drives_ok=12 pool_PoolDR_used=67.80%;80;90;0;100
```

---

# Tested Hardware

The plugin has been tested on:

| Hardware | Firmware | Status |
|----------|----------|--------|
| IBM FlashSystem | Storage Virtualize 9.1.0.4 | ✅ Tested |

Additional hardware and firmware versions are welcome. Feel free to open an issue or submit a pull request if you've successfully tested the plugin on another platform.

---

# Roadmap

## Version 1.x

- ✅ REST API monitoring
- ✅ Node canisters
- ✅ Drive health
- ✅ Storage pools
- ✅ Pool capacity thresholds
- ✅ Enclosure monitoring
- ✅ Power supplies
- ✅ Batteries

## Planned Features

- FC port monitoring
- Host port monitoring
- Replication health
- Volume monitoring
- Additional enclosure hardware checks
- Improved verbose output

---

# Contributing

Bug reports, feature requests and pull requests are welcome.

If you successfully test the plugin on another FlashSystem model or Storage Virtualize version, please consider contributing your results.

---
---

# Disclaimer

This project is an independent open-source Nagios plugin and is **not affiliated with, endorsed by, or supported by IBM**.

IBM®, FlashSystem®, and Storage Virtualize® are trademarks of International Business Machines Corporation.

Use this software at your own risk. Always test new versions in a non-production environment before deploying them into production.

# License

This project is licensed under the MIT License.

See the **LICENSE** file for details.
