---
name: Register issue
about: Report a wrong, missing, unsafe, or unsupported register definition
title: "[Register] "
labels: register, compatibility
assignees: ""
---

## Register

- Register key, if known:
- Address, if known:
- Read or write:
- Data type or unit, if known:
- Current metadata, if known:

## Device

- Heat-pump model:
- Controller or Navigator version:
- Firmware version:
- Active heating circuits:
- Zone modules and rooms:
- Library version:
- `pymodbus` version:

## Observed behavior

Describe the value, exception, unsupported address, encode/decode issue, or validation problem.

## Expected behavior

Describe what should be returned or how the register should be gated.

## Evidence

Attach redacted logs, diagnostics, or read-only Modbus observations.
Remove credentials, hostnames, IP addresses, and serial numbers before posting.

## Safety note

Do not test writes to EEPROM-sensitive, service, or unknown registers unless a maintainer explicitly asks for a controlled reproduction.
