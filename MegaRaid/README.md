# MegaRAID Disk Status

Small Debian/Ubuntu-friendly tool for showing physical MegaRAID disk status in a clean table.

Reports include:

```text
by WiseSoft ©2026
```

## Files to copy

Copy these two files to the target machine:

```text
megaraid-state-disk.sh
megaraid-state-disk.py
```

The other files in this folder are not required on the target machine:

```text
__pycache__/
```

That folder is only generated Python cache files.

## Requirements

Required:

```bash
sudo apt update
sudo apt install python3
```

Also required:

```text
storcli
```

Install `storcli` using the package/source appropriate for your RAID controller vendor or server distribution.

Optional, but recommended for the `Life left` column:

```bash
sudo apt install smartmontools
```

Without `smartctl`, the script still prints the storcli-based health table, but `Life left` will show `smartctl missing`.

## Tools Used

The report is created with these tools:

```text
python3   Runs the parser, formats the report, and creates the zip archive.
storcli   Reads MegaRAID controller, virtual drive, enclosure, and physical disk state.
smartctl  Reads per-disk SMART health, SSD lifetime, power-on hours, write counters, and error logs.
sh        Runs the wrapper script on Debian/Ubuntu.
awk       Adds color highlighting to interactive console output.
find      Removes loose .txt and .log files after the zip archive has been created.
readlink  Resolves the wrapper path when launched through a symlink.
date      Creates the timestamp used for output filenames.
cp        Copies storcli.log to a timestamped debug log before zipping.
```

`python3`, `sh`, `awk`, `find`, `readlink`, `date`, and `cp` are normally available on a standard Debian/Ubuntu system. `storcli` must be installed separately. `smartctl` is provided by `smartmontools`.

## Install

Example install location:

```bash
sudo mkdir -p /opt/megaraid-tools
sudo cp megaraid-state-disk.sh megaraid-state-disk.py /opt/megaraid-tools/
sudo chmod +x /opt/megaraid-tools/megaraid-state-disk.sh
sudo chmod +x /opt/megaraid-tools/megaraid-state-disk.py
```

Optional convenience symlink:

```bash
sudo ln -sf /opt/megaraid-tools/megaraid-state-disk.sh /usr/local/bin/megaraid-state-disk
```

## Usage

Default controller `0`:

```bash
sudo /opt/megaraid-tools/megaraid-state-disk.sh
```

Or, if you created the symlink:

```bash
sudo megaraid-state-disk
```

Specific controller:

```bash
sudo megaraid-state-disk -c 0
sudo megaraid-state-disk -c 1
```

Skip `smartctl` lookup:

```bash
sudo megaraid-state-disk --no-smartctl
```

Use another Linux block device for `smartctl` MegaRAID passthrough:

```bash
sudo megaraid-state-disk --device /dev/sdb
```

When called through `megaraid-state-disk.sh`, the output is printed to the terminal and also saved to disk.

Interactive terminal output is colorized:

```text
green   OK
yellow  WARN
red     CRITICAL
cyan    section headings
```

Saved report files are plain text without color codes. Disable terminal colors with:

```bash
NO_COLOR=1 sudo megaraid-state-disk
MEGARAID_COLOR=never sudo megaraid-state-disk
```

By default, each run creates one zip archive next to the installed script:

```text
/opt/megaraid-tools/output/YYYYMMDD-HHMMSS.zip
```

The zip file contains the report and the raw evidence files from that same run. After the zip has been created, loose `.txt` and `.log` files are removed from the output folder.

If `storcli` creates its own `storcli.log`, that log is included in the zip:

```text
storcli.log
storcli-debug-YYYYMMDD-HHMMSS.log
```

The script also saves the raw `storcli` command output used for parsing inside the zip:

```text
storcli-c0-show-YYYYMMDD-HHMMSS.txt
storcli-c0-eall-sall-show-YYYYMMDD-HHMMSS.txt
storcli-c0-eall-sall-show-all-YYYYMMDD-HHMMSS.txt
```

Raw `smartctl` output is saved once per disk inside the zip, using the same timestamp as the table report:

```text
smartctl-megaraid-DID-YYYYMMDD-HHMMSS.txt
```

These raw files are useful for auditing exactly which SMART attribute produced the `Life left` value.

Use `MEGARAID_OUTPUT_DIR` to choose another directory:

```bash
sudo MEGARAID_OUTPUT_DIR=/var/log/megaraid-tools megaraid-state-disk
```

## Output

Example:

```text
Controller:
  Status: OK
  Product: AVAGO MegaRAID SAS 9361-8i
  Serial: SV51010047
  Virtual drive 0/0: RAID10 Optl 1.861 TB
  Enclosure: OK

Overall status: WARN
Disks: 4 total, 0 critical, 1 warning

Action list:
  WARN: 252:0 DID 8 SN 200226072B60: life 20%

Status  Disk   DID  State  Life left  Reliability  POH    Cycles  Writes   Temp  SMART   MediaErr  PredFail  Realloc  Pending  Uncorr  CRC  SelfTest   Serial        Model          Note
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
WARN    252:0  8    Onln   20%        high         29665  35      111.7TB  34C   PASSED  0         0         0        0        0       0    completed  200226072B60  MTFDDAK1T0TDL  life 20%

Raw smartctl files:
  DID 8: smartctl-megaraid-8-YYYYMMDD-HHMMSS.txt
```

Column meaning:

```text
Status     Derived verdict: OK, WARN, or CRITICAL
Disk       Enclosure ID and slot number
DID        MegaRAID device ID, used for smartctl passthrough
State      Controller state, for example Onln
Life left  SSD lifetime/wear value from smartctl when available
Reliability Confidence in the Life left value
POH        Power-on hours from smartctl
Cycles     Power cycle count from smartctl
Writes     Approximate host writes calculated from SMART attributes
Temp       Drive temperature from storcli
SMART      SMART health result from smartctl
MediaErr   Controller media error count
PredFail   Controller predictive failure count
Realloc    SMART reallocated sector/event count
Pending    SMART pending sector/ECC count
Uncorr     SMART reported/offline uncorrectable count
CRC        SMART UDMA CRC error count
SelfTest   Latest SMART self-test status
Serial     Drive serial number
Model      Drive model
Note       Reason for WARN or CRITICAL
```

`Life left` reliability:

```text
high    A direct lifetime-left style SMART attribute was found, or NVMe Percentage Used was converted to remaining life.
medium  A normalized vendor wear indicator was used.
low     Only the generic SMART health result was available.
none    No usable SMART life/wear value was available.
```

## Commands used internally

The script runs:

```bash
storcli /c0 show
storcli /c0/eall/sall show
storcli /c0/eall/sall show all
smartctl -a -d megaraid,DID /dev/sda
```

The controller number and smartctl device can be changed with `--controller` and `--device`.
