#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Disk:
    disk: str
    did: str
    state: str
    dg: str
    size: str
    disk_type: str
    model: str
    serial: str = "-"
    firmware: str = "-"
    temp: str = "-"
    smart_alert: str = "-"
    media_err: str = "-"
    other_err: str = "-"
    pred_fail: str = "-"
    life_left: str = "-"
    life_source: str = "-"
    life_reliability: str = "-"
    smart_health: str = "-"
    power_on_hours: str = "-"
    power_cycles: str = "-"
    writes_tb: str = "-"
    realloc: str = "-"
    pending: str = "-"
    offline_unc: str = "-"
    reported_unc: str = "-"
    crc_errors: str = "-"
    smart_error_log: str = "-"
    selftest: str = "-"
    status: str = "-"
    note: str = "-"
    smartctl_file: str = "-"


@dataclass
class ControllerSummary:
    product: str = "-"
    serial: str = "-"
    virtual_drive: str = "-"
    virtual_drive_state: str = "-"
    virtual_drive_type: str = "-"
    virtual_drive_size: str = "-"
    enclosure_state: str = "-"
    status: str = "OK"
    note: str = "-"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def run_command(command: List[str]) -> str:
    cwd = os.environ.get("MEGARAID_STORCLI_LOG_DIR") if command[0] == "storcli" else None
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL, cwd=cwd)
    except FileNotFoundError:
        fail(f"Missing command: {command[0]}")
    except subprocess.CalledProcessError:
        fail(f"Command failed: {' '.join(command)}")


def save_raw_text(filename: str, text: str) -> str:
    output_dir = os.environ.get("MEGARAID_OUTPUT_DIR")
    if not output_dir:
        return "-"

    path = os.path.join(output_dir, filename)
    try:
        with open(path, "w", encoding="utf-8", errors="replace") as handle:
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
    except OSError:
        return "save failed"

    return os.path.basename(path)


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as exc:
        fail(f"Cannot read {path}: {exc}")


def clean_value(line: str) -> str:
    return line.split("=", 1)[1].strip() if "=" in line else "-"


def parse_pd_table(text: str) -> Dict[str, Disk]:
    disks: Dict[str, Disk] = {}

    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14 or not re.match(r"^\d+:\d+$", parts[0]) or not parts[1].isdigit():
            continue

        model_parts = parts[11:-2]
        disk = Disk(
            disk=parts[0],
            did=parts[1],
            state=parts[2],
            dg=parts[3],
            size=f"{parts[4]} {parts[5]}",
            disk_type=f"{parts[6]}/{parts[7]}",
            model=" ".join(model_parts) if model_parts else "-",
        )
        disks[disk.disk] = disk

    return disks


def parse_details(text: str, disks: Dict[str, Disk]) -> None:
    current: Optional[Disk] = None

    for line in text.splitlines():
        match = re.match(r"^Drive /c\d+/e(\d+)/s(\d+) :", line)
        if match:
            current = disks.get(f"{match.group(1)}:{match.group(2)}")
            continue

        if current is None:
            continue

        if line.startswith("Media Error Count"):
            current.media_err = clean_value(line)
        elif line.startswith("Other Error Count"):
            current.other_err = clean_value(line)
        elif line.startswith("Drive Temperature"):
            current.temp = clean_value(line).split("(", 1)[0].replace(" ", "")
        elif line.startswith("Predictive Failure Count"):
            current.pred_fail = clean_value(line)
        elif line.startswith("S.M.A.R.T alert flagged by drive"):
            current.smart_alert = clean_value(line)
        elif re.match(r"^SN\s*=", line):
            current.serial = clean_value(line)
        elif line.startswith("Model Number"):
            current.model = clean_value(line)
        elif line.startswith("Firmware Revision"):
            current.firmware = clean_value(line)


def parse_controller_summary(text: str) -> ControllerSummary:
    summary = ControllerSummary()

    for line in text.splitlines():
        if line.startswith("Product Name"):
            summary.product = clean_value(line)
        elif line.startswith("Serial Number"):
            summary.serial = clean_value(line)

        parts = line.split()
        if len(parts) >= 9 and re.match(r"^\d+/\d+$", parts[0]):
            summary.virtual_drive = parts[0]
            summary.virtual_drive_type = parts[1]
            summary.virtual_drive_state = parts[2]
            summary.virtual_drive_size = f"{parts[8]} {parts[9]}" if len(parts) > 9 else parts[8]

        if len(parts) >= 3 and parts[0].isdigit() and parts[1] in ("OK", "Critical", "Failed"):
            summary.enclosure_state = parts[1]

    return summary


def classify_controller(summary: ControllerSummary) -> None:
    problems: List[str] = []

    if summary.virtual_drive_state not in ("-", "Optl"):
        problems.append(f"virtual drive {summary.virtual_drive} state {summary.virtual_drive_state}")
    if summary.enclosure_state not in ("-", "OK"):
        problems.append(f"enclosure {summary.enclosure_state}")

    if problems:
        summary.status = "CRITICAL"
        summary.note = "; ".join(problems)
    else:
        summary.status = "OK"
        summary.note = "-"


def timestamped_filename(prefix: str, suffix: str = ".txt") -> str:
    timestamp = os.environ.get("MEGARAID_REPORT_TIMESTAMP")
    if timestamp:
        return f"{prefix}-{timestamp}{suffix}"
    return f"{prefix}{suffix}"


def save_raw_smartctl(did: str, output: str) -> str:
    return save_raw_text(timestamped_filename(f"smartctl-megaraid-{did}"), output)


def smart_attr_raw(output: str, names: List[str]) -> str:
    wanted = set(names)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 10 and parts[0].isdigit() and parts[1] in wanted:
            return parts[-1]
    return "-"


def smart_attr_value(output: str, names: List[str]) -> str:
    wanted = set(names)
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 10 and parts[0].isdigit() and parts[1] in wanted:
            return parts[3] if parts[3].isdigit() else "-"
    return "-"


def parse_int(value: str) -> Optional[int]:
    match = re.search(r"\d+", value)
    if not match:
        return None
    return int(match.group(0))


def format_tb(bytes_value: float) -> str:
    return f"{bytes_value / 1_000_000_000_000:.1f}TB"


def smart_writes_tb(output: str) -> str:
    lbas = smart_attr_raw(output, ["Total_LBAs_Written"])
    lbas_int = parse_int(lbas)
    if lbas_int is not None:
        return format_tb(lbas_int * 512)

    host_writes_32mib = smart_attr_raw(output, ["Host_Writes_32MiB"])
    host_writes_int = parse_int(host_writes_32mib)
    if host_writes_int is not None:
        return format_tb(host_writes_int * 32 * 1024 * 1024)

    return "-"


def parse_smart_life(output: str) -> Tuple[str, str, str]:
    for line in output.splitlines():
        match = re.search(r"Percentage Used:\s+(\d+)%", line)
        if match:
            used = int(match.group(1))
            remaining = max(0, 100 - used)
            return f"{remaining}%", "Percentage Used", "high"

    raw_value_attrs = {
        "Percent_Lifetime_Remain",
        "Remaining_Lifetime_Perc",
        "SSD_Life_Left",
    }
    normalized_value_attrs = {
        "Media_Wearout_Indicator",
    }

    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 10 or not parts[0].isdigit():
            continue

        attr_name = parts[1]
        if attr_name in raw_value_attrs:
            raw_value = parts[-1]
            match = re.search(r"\d+", raw_value)
            if match:
                return f"{match.group(0)}%", f"{attr_name} RAW_VALUE", "high"
            if parts[3].isdigit():
                return f"{int(parts[3])}%", f"{attr_name} VALUE", "medium"

        if attr_name in normalized_value_attrs and parts[3].isdigit():
            return f"{int(parts[3])}%", f"{attr_name} VALUE", "medium"

    health = re.search(r"SMART overall-health self-assessment test result:\s*(.+)", output)
    if health:
        return f"SMART {health.group(1).strip()}", "SMART health only", "low"
    if "mandatory smart command failed" in output.lower():
        return "unreadable", "smartctl command failed", "none"

    return "-", "no known life attribute", "none"


def parse_smart_summary(output: str) -> Dict[str, str]:
    summary = {
        "smart_health": "-",
        "power_on_hours": smart_attr_raw(output, ["Power_On_Hours"]),
        "power_cycles": smart_attr_raw(output, ["Power_Cycle_Count"]),
        "writes_tb": smart_writes_tb(output),
        "realloc": smart_attr_raw(output, ["Reallocated_Sector_Ct", "Reallocated_Event_Count"]),
        "pending": smart_attr_raw(output, ["Current_Pending_Sector", "Current_Pending_ECC_Cnt"]),
        "offline_unc": smart_attr_raw(output, ["Offline_Uncorrectable"]),
        "reported_unc": smart_attr_raw(output, ["Reported_Uncorrect", "Uncorrectable_Error_Cnt"]),
        "crc_errors": smart_attr_raw(output, ["UDMA_CRC_Error_Count"]),
        "smart_error_log": "-",
        "selftest": "-",
    }

    health = re.search(r"SMART overall-health self-assessment test result:\s*(.+)", output)
    if health:
        summary["smart_health"] = health.group(1).strip()

    if "No Errors Logged" in output:
        summary["smart_error_log"] = "none"
    elif "SMART Error Log" in output:
        summary["smart_error_log"] = "present"

    for line in output.splitlines():
        if re.match(r"^#\s*1\s+", line):
            parts = line.split()
            if "Completed" in parts:
                summary["selftest"] = "completed"
            elif len(parts) >= 4:
                summary["selftest"] = " ".join(parts[2:5])
            break
        if line.startswith("No self-tests have been logged"):
            summary["selftest"] = "none logged"

    return summary


def smartctl_life_left(did: str, device: str) -> Tuple[str, str, str, str, Dict[str, str]]:
    empty_summary = parse_smart_summary("")
    if shutil.which("smartctl") is None:
        return "smartctl missing", "-", "none", "-", empty_summary

    result = subprocess.run(
        ["smartctl", "-a", "-d", f"megaraid,{did}", device],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = result.stdout
    if result.stderr:
        output = output + ("\n" if output and not output.endswith("\n") else "") + result.stderr
    raw_file = save_raw_smartctl(did, output)
    if not output:
        return "unreadable", "no smartctl output", "none", raw_file, empty_summary

    life_left, life_source, life_reliability = parse_smart_life(output)
    return life_left, life_source, life_reliability, raw_file, parse_smart_summary(output)


def parse_percent(value: str) -> Optional[int]:
    match = re.search(r"(\d+)%", value)
    if not match:
        return None
    return int(match.group(1))


def is_nonzero(value: str) -> bool:
    match = re.search(r"\d+", value)
    return bool(match and int(match.group(0)) != 0)


def classify_disk(disk: Disk) -> None:
    problems: List[str] = []
    warnings: List[str] = []

    if disk.state not in ("Onln", "UGood"):
        problems.append(f"controller state {disk.state}")
    if disk.smart_alert == "Yes":
        problems.append("storcli SMART alert")
    if is_nonzero(disk.media_err):
        problems.append(f"media errors {disk.media_err}")
    if is_nonzero(disk.pred_fail):
        problems.append(f"predictive failures {disk.pred_fail}")
    if disk.smart_health not in ("-", "PASSED"):
        problems.append(f"SMART {disk.smart_health}")

    life_pct = parse_percent(disk.life_left)
    if life_pct is not None:
        if life_pct <= 10:
            problems.append(f"life {life_pct}%")
        elif life_pct <= 25:
            warnings.append(f"life {life_pct}%")
        elif life_pct <= 40:
            warnings.append(f"life {life_pct}%")

    for label, value in [
        ("reported uncorrect", disk.reported_unc),
        ("reallocated", disk.realloc),
        ("pending", disk.pending),
        ("offline uncorrectable", disk.offline_unc),
        ("crc", disk.crc_errors),
    ]:
        if is_nonzero(value):
            warnings.append(f"{label} {value}")

    if disk.smart_error_log == "present":
        warnings.append("SMART error log present")

    if problems:
        disk.status = "CRITICAL"
        disk.note = "; ".join(problems + warnings)
    elif warnings:
        disk.status = "WARN"
        disk.note = "; ".join(warnings)
    else:
        disk.status = "OK"
        disk.note = "-"


def print_controller_summary(summary: ControllerSummary) -> None:
    if summary == ControllerSummary():
        return

    print("Controller:")
    print(f"  Status: {summary.status}")
    print(f"  Product: {summary.product}")
    print(f"  Serial: {summary.serial}")
    if summary.virtual_drive != "-":
        print(
            f"  Virtual drive {summary.virtual_drive}: "
            f"{summary.virtual_drive_type} {summary.virtual_drive_state} {summary.virtual_drive_size}"
        )
    if summary.enclosure_state != "-":
        print(f"  Enclosure: {summary.enclosure_state}")
    if summary.note != "-":
        print(f"  Note: {summary.note}")
    print()


def print_table(disks: List[Disk]) -> None:
    headers = [
        "Status",
        "Disk",
        "DID",
        "State",
        "Life left",
        "Reliability",
        "POH",
        "Cycles",
        "Writes",
        "Temp",
        "SMART",
        "MediaErr",
        "PredFail",
        "Realloc",
        "Pending",
        "Uncorr",
        "CRC",
        "SelfTest",
        "Serial",
        "Model",
        "Note",
    ]
    rows = [
        [
            disk.status,
            disk.disk,
            disk.did,
            disk.state,
            disk.life_left,
            disk.life_reliability,
            disk.power_on_hours,
            disk.power_cycles,
            disk.writes_tb,
            disk.temp,
            disk.smart_health,
            disk.media_err,
            disk.pred_fail,
            disk.realloc,
            disk.pending,
            disk.reported_unc if disk.reported_unc != "-" else disk.offline_unc,
            disk.crc_errors,
            disk.selftest,
            disk.serial,
            disk.model,
            disk.note,
        ]
        for disk in disks
    ]

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def format_row(row: List[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    print(format_row(headers))
    print("-" * len(format_row(headers)))
    for row in rows:
        print(format_row(row))


def print_summary(disks: List[Disk], controller: ControllerSummary) -> None:
    critical = [disk for disk in disks if disk.status == "CRITICAL"]
    warnings = [disk for disk in disks if disk.status == "WARN"]

    if controller.status == "CRITICAL" or critical:
        overall = "CRITICAL"
    elif warnings:
        overall = "WARN"
    else:
        overall = "OK"

    print(f"Overall status: {overall}")
    print(f"Disks: {len(disks)} total, {len(critical)} critical, {len(warnings)} warning")

    if controller.status == "CRITICAL" or critical or warnings:
        print()
        print("Action list:")
        if controller.status == "CRITICAL":
            print(f"  CRITICAL: controller: {controller.note}")
        for disk in critical + warnings:
            identity = f"{disk.disk} DID {disk.did} SN {disk.serial}"
            print(f"  {disk.status}: {identity}: {disk.note}")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Show MegaRAID physical disk status in a clean table.",
    )
    parser.add_argument("controller_arg", nargs="?", help="controller number, default: 0")
    parser.add_argument("-c", "--controller", default=None, help="controller number, default: 0")
    parser.add_argument("--device", default="/dev/sda", help="device for smartctl passthrough, default: /dev/sda")
    parser.add_argument("--no-smartctl", action="store_true", help="skip smartctl life-left lookup")
    parser.add_argument("--pd-log", help='read "storcli /cN/eall/sall show" output from file')
    parser.add_argument("--all-log", help='read "storcli /cN/eall/sall show all" output from file')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    controller = args.controller or args.controller_arg or "0"
    if not controller.isdigit():
        fail("Controller must be a number")

    if bool(args.pd_log) != bool(args.all_log):
        fail("--pd-log and --all-log must be used together")

    if args.pd_log and args.all_log:
        ctrl_summary = ControllerSummary()
        pd_text = read_text(args.pd_log)
        all_text = read_text(args.all_log)
    else:
        if shutil.which("storcli") is None:
            fail("Missing command: storcli")
        ctrl_text = run_command(["storcli", f"/c{controller}", "show"])
        ctrl_summary = parse_controller_summary(ctrl_text)
        pd_text = run_command(["storcli", f"/c{controller}/eall/sall", "show"])
        all_text = run_command(["storcli", f"/c{controller}/eall/sall", "show", "all"])
        save_raw_text(timestamped_filename(f"storcli-c{controller}-show"), ctrl_text)
        save_raw_text(timestamped_filename(f"storcli-c{controller}-eall-sall-show"), pd_text)
        save_raw_text(timestamped_filename(f"storcli-c{controller}-eall-sall-show-all"), all_text)

    disks_by_id = parse_pd_table(pd_text)
    if not disks_by_id:
        fail("No physical drives found in storcli output")

    parse_details(all_text, disks_by_id)
    disks = sorted(disks_by_id.values(), key=lambda disk: [int(part) for part in disk.disk.split(":")])

    if not args.no_smartctl:
        for disk in disks:
            (
                disk.life_left,
                disk.life_source,
                disk.life_reliability,
                disk.smartctl_file,
                smart_summary,
            ) = smartctl_life_left(disk.did, args.device)
            disk.smart_health = smart_summary["smart_health"]
            disk.power_on_hours = smart_summary["power_on_hours"]
            disk.power_cycles = smart_summary["power_cycles"]
            disk.writes_tb = smart_summary["writes_tb"]
            disk.realloc = smart_summary["realloc"]
            disk.pending = smart_summary["pending"]
            disk.offline_unc = smart_summary["offline_unc"]
            disk.reported_unc = smart_summary["reported_unc"]
            disk.crc_errors = smart_summary["crc_errors"]
            disk.smart_error_log = smart_summary["smart_error_log"]
            disk.selftest = smart_summary["selftest"]

    for disk in disks:
        classify_disk(disk)
    classify_controller(ctrl_summary)

    print_controller_summary(ctrl_summary)
    print_summary(disks, ctrl_summary)
    print_table(disks)

    print()
    print("Life source:")
    for disk in disks:
        print(f"  DID {disk.did}: {disk.life_left} from {disk.life_source}")

    saved_files = [disk.smartctl_file for disk in disks if disk.smartctl_file not in ("-", "save failed")]
    if saved_files:
        print()
        print("Raw smartctl files:")
        for disk in disks:
            if disk.smartctl_file not in ("-", "save failed"):
                print(f"  DID {disk.did}: {disk.smartctl_file}")


if __name__ == "__main__":
    main()
