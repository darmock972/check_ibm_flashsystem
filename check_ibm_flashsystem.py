#!/usr/bin/env python3
"""
check_ibm_flashsystem.py - Nagios Core plugin for IBM FlashSystem / Storage Virtualize

Version: 1.0.2-secure

Checks:
- REST API connectivity and authentication
- System name and code level
- Node canisters
- Drives
- Storage pools status and utilization
- Enclosure status/counts
- Power supplies
- Batteries

Tested with IBM FlashSystem / Storage Virtualize 9.1.0.4.
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

PLUGIN_VERSION = "1.0.2-secure"

STATUS_TEXT = {
    OK: "OK",
    WARNING: "WARNING",
    CRITICAL: "CRITICAL",
    UNKNOWN: "UNKNOWN",
}


class FlashSystemError(Exception):
    pass


class FlashSystemAPI:
    def __init__(self, host: str, username: str, password: str, port: int = 7443, timeout: int = 10):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.token: Optional[str] = None

    def url(self, endpoint: str) -> str:
        return f"https://{self.host}:{self.port}/rest/v1/{endpoint}"

    def post(self, endpoint: str, auth: bool = True) -> Any:
        headers = {"Accept": "application/json", "User-Agent": f"check_ibm_flashsystem/{PLUGIN_VERSION}"}

        if auth:
            if not self.token:
                raise FlashSystemError("API token is missing")
            headers["X-Auth-Token"] = self.token
        else:
            headers["X-Auth-Username"] = self.username
            headers["X-Auth-Password"] = self.password

        try:
            response = requests.post(
                self.url(endpoint),
                headers=headers,
                json={},
                verify=False,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectTimeout:
            raise FlashSystemError("Connection timed out")
        except requests.exceptions.ReadTimeout:
            raise FlashSystemError("REST API read timed out")
        except requests.exceptions.ConnectionError as exc:
            raise FlashSystemError(f"Cannot connect to REST API: {exc}")
        except requests.exceptions.HTTPError as exc:
            raise FlashSystemError(f"HTTP error from REST API: {exc}")
        except ValueError as exc:
            raise FlashSystemError(f"Invalid JSON from REST API: {exc}")

    def login(self) -> None:
        data = self.post("auth", auth=False)
        if not isinstance(data, dict) or not data.get("token"):
            raise FlashSystemError("No auth token returned")
        self.token = data["token"]

    def system(self) -> Dict[str, Any]:
        return first_dict(self.post("lssystem"))

    def nodes(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsnodecanister"))

    def drives(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsdrive"))

    def pools(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsmdiskgrp"))

    def enclosures(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsenclosure"))

    def psus(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsenclosurepsu"))

    def batteries(self) -> List[Dict[str, Any]]:
        return as_list(self.post("lsenclosurebattery"))


class NagiosResult:
    def __init__(self, system_name: str = "IBM FlashSystem", json_output: bool = False, verbose: bool = False):
        self.system_name = system_name
        self.json_output = json_output
        self.verbose = verbose
        self.messages: List[Tuple[int, str]] = []
        self.summary_parts: List[str] = []
        self.verbose_parts: List[str] = []
        self.perfdata: List[str] = []
        self.details: Dict[str, Any] = {}

    def set_system_name(self, name: str) -> None:
        self.system_name = name or self.system_name

    def add_summary(self, text: str) -> None:
        self.summary_parts.append(text)

    def add_verbose(self, text: str) -> None:
        if self.verbose:
            self.verbose_parts.append(text)

    def add_perfdata(self, text: str) -> None:
        self.perfdata.append(text)

    def ok(self, message: str) -> None:
        self.messages.append((OK, message))

    def warning(self, message: str) -> None:
        self.messages.append((WARNING, message))

    def critical(self, message: str) -> None:
        self.messages.append((CRITICAL, message))

    def unknown(self, message: str) -> None:
        self.messages.append((UNKNOWN, message))

    def exit_code(self) -> int:
        if any(code == CRITICAL for code, _ in self.messages):
            return CRITICAL
        if any(code == WARNING for code, _ in self.messages):
            return WARNING
        if any(code == UNKNOWN for code, _ in self.messages):
            return UNKNOWN
        return OK

    def finish(self) -> None:
        code = self.exit_code()
        status = STATUS_TEXT[code]

        if self.json_output:
            payload = {
                "status": status,
                "exit_code": code,
                "system": self.system_name,
                "summary": self.summary_parts,
                "messages": [{"state": STATUS_TEXT[c], "message": m} for c, m in self.messages],
                "perfdata": self.perfdata,
                "details": self.details,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            sys.exit(code)

        problem_messages = [msg for c, msg in self.messages if c != OK]
        if problem_messages:
            text = f"{status} - {self.system_name}: " + ", ".join(problem_messages)
        else:
            text = f"OK - {self.system_name}: " + ", ".join(self.summary_parts)

        if self.verbose and self.verbose_parts:
            text += ", " + ", ".join(self.verbose_parts)

        if self.perfdata:
            text += " | " + " ".join(self.perfdata)

        print(text)
        sys.exit(code)


def as_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def first_dict(data: Any) -> Dict[str, Any]:
    items = as_list(data)
    return items[0] if items else {}


def capacity_to_tb(value: str) -> Optional[float]:
    if not value:
        return None
    match = re.match(r"^([\d.]+)\s*(MB|GB|TB|PB)$", str(value).strip(), re.I)
    if not match:
        return None

    number = float(match.group(1))
    unit = match.group(2).upper()

    if unit == "MB":
        return number / 1024 / 1024
    if unit == "GB":
        return number / 1024
    if unit == "TB":
        return number
    if unit == "PB":
        return number * 1024
    return None


def safe_perf_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def short_code_level(value: str) -> str:
    match = re.match(r"^(\d+(?:\.\d+){1,3})", str(value))
    return match.group(1) if match else str(value)


def read_password(args: argparse.Namespace) -> str:
    supplied = [bool(args.password_file), bool(args.password_env)]
    if sum(supplied) != 1:
        raise FlashSystemError("Specify exactly one of --password-file or --password-env")

    if args.password_file:
        try:
            with open(args.password_file, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError as exc:
            raise FlashSystemError(f"Cannot read password file: {exc}")

    env_value = os.environ.get(args.password_env)
    if not env_value:
        raise FlashSystemError(f"Environment variable {args.password_env} is empty or missing")
    return env_value


def check_nodes(api: FlashSystemAPI, result: NagiosResult) -> None:
    nodes = api.nodes()
    bad = []

    for node in nodes:
        name = node.get("name", node.get("node_name", node.get("id", "unknown")))
        status = str(node.get("status", "")).lower()
        if status not in ("online", "active"):
            bad.append(f"Node {name} status={status or 'unknown'}")

    total = len(nodes)
    ok_count = total - len(bad)
    result.details["nodes"] = {"ok": ok_count, "total": total, "bad": bad}
    result.add_summary(f"Nodes {ok_count}/{total}")
    result.add_perfdata(f"nodes_ok={ok_count}")
    result.add_perfdata(f"nodes_total={total}")

    for item in bad:
        result.critical(item)


def check_drives(api: FlashSystemAPI, result: NagiosResult) -> None:
    drives = api.drives()
    bad = []

    for drive in drives:
        drive_id = drive.get("id", "unknown")
        status = str(drive.get("status", "")).lower()
        use = drive.get("use", "")
        if status != "online":
            bad.append(f"Drive {drive_id} status={status or 'unknown'} use={use}")

    total = len(drives)
    ok_count = total - len(bad)
    result.details["drives"] = {"ok": ok_count, "total": total, "bad": bad}
    result.add_summary(f"Drives {ok_count}/{total}")
    result.add_perfdata(f"drives_ok={ok_count}")
    result.add_perfdata(f"drives_total={total}")

    for item in bad:
        result.critical(item)


def check_pools(api: FlashSystemAPI, result: NagiosResult, warn: float, crit: float) -> None:
    pools = api.pools()
    pool_details = []

    for pool in pools:
        name = pool.get("name", "unknown")
        status = str(pool.get("status", "unknown")).lower()
        capacity_tb = capacity_to_tb(pool.get("capacity", ""))
        used_tb = capacity_to_tb(pool.get("used_capacity", ""))

        if status != "online":
            result.critical(f"Pool {name} status={status}")

        used_percent = None
        if capacity_tb and used_tb is not None:
            used_percent = (used_tb / capacity_tb) * 100
            perf_name = safe_perf_name(name)
            result.add_perfdata(f"pool_{perf_name}_used={used_percent:.2f}%;{warn};{crit};0;100")

            if used_percent >= crit:
                result.critical(f"Pool {name} {used_percent:.1f}% used")
            elif used_percent >= warn:
                result.warning(f"Pool {name} {used_percent:.1f}% used")

            result.add_summary(f"{name} {used_percent:.1f}%")
        else:
            result.warning(f"Pool {name} capacity fields unavailable")

        pool_details.append({
            "name": name,
            "status": status,
            "capacity": pool.get("capacity"),
            "used_capacity": pool.get("used_capacity"),
            "used_percent": used_percent,
        })

    result.details["pools"] = pool_details
    if not pools:
        result.warning("No pools returned by lsmdiskgrp")


def check_enclosures(api: FlashSystemAPI, result: NagiosResult) -> None:
    enclosures = api.enclosures()
    bad = []

    for enc in enclosures:
        enc_id = enc.get("id", "unknown")
        status = str(enc.get("status", "unknown")).lower()
        if status != "online":
            bad.append(f"Enclosure {enc_id} status={status}")
        result.add_verbose(
            f"Enclosure {enc_id} MTM={enc.get('product_MTM', 'unknown')} serial={enc.get('serial_number', 'unknown')}"
        )

    ok_count = len(enclosures) - len(bad)
    result.details["enclosures"] = {"ok": ok_count, "total": len(enclosures), "bad": bad}
    result.add_summary(f"Enclosures {ok_count}/{len(enclosures)}")
    result.add_perfdata(f"enclosures_ok={ok_count}")
    result.add_perfdata(f"enclosures_total={len(enclosures)}")

    for item in bad:
        result.critical(item)


def check_psus(api: FlashSystemAPI, result: NagiosResult) -> None:
    psus = api.psus()
    bad = []

    for psu in psus:
        enc_id = psu.get("enclosure_id", "unknown")
        psu_id = psu.get("PSU_id", "unknown")
        status = str(psu.get("status", "unknown")).lower()
        if status != "online":
            bad.append(f"PSU {psu_id} enclosure {enc_id} status={status}")

    ok_count = len(psus) - len(bad)
    result.details["psus"] = {"ok": ok_count, "total": len(psus), "bad": bad}
    result.add_summary(f"PSU {ok_count}/{len(psus)}")
    result.add_perfdata(f"psus_ok={ok_count}")
    result.add_perfdata(f"psus_total={len(psus)}")

    for item in bad:
        result.critical(item)


def check_batteries(api: FlashSystemAPI, result: NagiosResult, min_charge: int) -> None:
    batteries = api.batteries()
    bad = []
    warn = []

    for battery in batteries:
        enc_id = battery.get("enclosure_id", "unknown")
        bat_id = battery.get("battery_id", "unknown")
        label = f"Battery {bat_id} enclosure {enc_id}"
        status = str(battery.get("status", "unknown")).lower()
        charging_status = str(battery.get("charging_status", "unknown")).lower()
        recondition_needed = str(battery.get("recondition_needed", "no")).lower()
        end_of_life_warning = str(battery.get("end_of_life_warning", "no")).lower()

        try:
            percent_charged = int(str(battery.get("percent_charged", "0")))
        except ValueError:
            percent_charged = 0

        if status != "online":
            bad.append(f"{label} status={status}")
        if recondition_needed == "yes":
            warn.append(f"{label} recondition needed")
        if end_of_life_warning == "yes":
            warn.append(f"{label} end-of-life warning")
        if percent_charged < min_charge:
            warn.append(f"{label} charge={percent_charged}%")

    ok_count = len(batteries) - len(bad)
    result.details["batteries"] = {"ok": ok_count, "total": len(batteries), "critical": bad, "warning": warn}
    result.add_summary(f"Batteries {ok_count}/{len(batteries)}")
    result.add_perfdata(f"batteries_ok={ok_count}")
    result.add_perfdata(f"batteries_total={len(batteries)}")

    for item in bad:
        result.critical(item)
    for item in warn:
        result.warning(item)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nagios plugin for IBM FlashSystem / Storage Virtualize REST API")
    parser.add_argument("-H", "--host", required=True, help="FlashSystem management IP or hostname")
    parser.add_argument("--port", type=int, default=7443, help="REST API port, default: 7443")
    parser.add_argument("-u", "--username", required=True, help="FlashSystem username")
    parser.add_argument("--password-file", help="File containing the password")
    parser.add_argument("--password-env", help="Environment variable containing the password")
    parser.add_argument("-w", "--warning", type=float, default=80.0, help="Pool utilization warning threshold, default: 80")
    parser.add_argument("-c", "--critical", type=float, default=90.0, help="Pool utilization critical threshold, default: 90")
    parser.add_argument("--battery-min-charge", type=int, default=80, help="Battery minimum charge warning threshold, default: 80")
    parser.add_argument("--timeout", type=int, default=10, help="REST API timeout in seconds, default: 10")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Nagios text")
    parser.add_argument("--version", action="version", version=f"check_ibm_flashsystem {PLUGIN_VERSION}")
    parser.add_argument("-v", "--verbose", action="store_true", help="Add verbose details to output")
    parser.add_argument("--ignore-enclosure", action="store_true", help="Skip enclosure check")
    parser.add_argument("--ignore-psu", action="store_true", help="Skip PSU check")
    parser.add_argument("--ignore-batteries", action="store_true", help="Skip battery check")
    parser.add_argument("--ignore-pools", action="store_true", help="Skip storage pool check")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.warning >= args.critical:
            raise FlashSystemError("Warning threshold must be lower than critical threshold")

        password = read_password(args)
        api = FlashSystemAPI(args.host, args.username, password, port=args.port, timeout=args.timeout)
        api.login()

        system = api.system()
        system_name = system.get("name", args.host)
        code_level = system.get("code_level", "unknown")

        result = NagiosResult(system_name=system_name, json_output=args.json, verbose=args.verbose)
        result.details["system"] = system
        result.add_summary(f"Code {short_code_level(code_level)}")
        result.add_verbose(f"Full code_level={code_level}")

        check_nodes(api, result)
        check_drives(api, result)

        if not args.ignore_pools:
            check_pools(api, result, args.warning, args.critical)

        if not args.ignore_enclosure:
            check_enclosures(api, result)

        if not args.ignore_psu:
            check_psus(api, result)

        if not args.ignore_batteries:
            check_batteries(api, result, args.battery_min_charge)

        result.finish()

    except FlashSystemError as exc:
        result = NagiosResult(system_name=args.host if "args" in locals() else "IBM FlashSystem", json_output=getattr(args, "json", False))
        result.unknown(str(exc))
        result.finish()
    except KeyboardInterrupt:
        print("UNKNOWN - Interrupted")
        sys.exit(UNKNOWN)
    except Exception as exc:
        print(f"UNKNOWN - Unexpected error: {exc}")
        sys.exit(UNKNOWN)


if __name__ == "__main__":
    main()
