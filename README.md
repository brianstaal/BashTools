# BashTools

Small operational tools for Linux server administration, diagnostics, and routine support tasks.

The repository is intended to collect focused command-line utilities that are easy to copy to a target Debian/Ubuntu machine, run from a shell, and inspect later through saved output files.

All tools should identify generated reports with:

```text
by WiseSoft ©2026
```

## Tools

### MegaRaid

Location:

```text
MegaRaid/
```

The MegaRaid tool reports MegaRAID physical disk and array health using `storcli` and, when available, `smartctl`.

It prints and saves a report containing:

```text
Controller status
Virtual drive / RAID state
Enclosure state
Per-disk OK / WARN / CRITICAL verdict
Disk state, serial number, model, temperature
SSD life-left percentage and reliability
Power-on hours, power cycles, approximate host writes
SMART health, SMART error counters, and latest self-test status
Raw storcli and smartctl evidence files
Timestamped zip archive for each run
```

Target files to copy:

```text
MegaRaid/megaraid-state-disk.sh
MegaRaid/megaraid-state-disk.py
```

Detailed install and usage notes are in:

```text
MegaRaid/README.md
```

## Generated Files

Generated reports and raw diagnostic output are ignored by git:

```text
MegaRaid/output/
__pycache__/
```
