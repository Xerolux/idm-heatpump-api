# IDM Register Map Invariants

This document records the protocol facts and engineering rules that must be
preserved when maintaining the IDM Modbus implementation. It exists because a
previous attempt to normalize overlapping address ranges changed official
addresses and datatypes, causing corrupt humidity and heating-circuit values.

## Source hierarchy

Use evidence in this order:

1. Official IDM Modbus documentation for the exact Navigator generation and
   firmware family.
2. An anonymized raw hardware capture showing the exact function code, start
   address, count, returned words, and independently verified device value.
3. Existing tested implementation behavior.
4. Community reports and third-party templates as leads only.

Do not infer a register change solely from address patterns, apparent range
overlaps, or third-party configuration screenshots.

## Reviewed primary documents

The following official IDM documents were compared during the issue-90 audit:

- `ma_de_812049_modbus-tcp_navigator-1.0-und-1.7.pdf`, register table dated
  2016-06-13, for Navigator 1.0/1.7.
- `Installation Modbus TCP Navigator`, register table dated 2020-03-10,
  Navigator 2.0 software 20.15-0.
- `Modbus TCP Navigator 2.0`, register table dated 2022-04-20, Navigator 2.0
  software 20.21-101.
- `docs/New/Modbus_TCP_NAVIGATOR_10.pdf`, Navigator 10 documentation dated
  2025-06-18.

The 2020, 2022, and 2025 tables consistently document the affected Navigator
2.0/10 addresses. The older Navigator 1.x table is a different map and must
remain isolated.

## Navigator 2.0/10 confirmed definitions

These values are stable across the reviewed official tables:

| Data point | Address | Datatype |
| --- | ---: | --- |
| Humidity sensor B31 | 1392 | FLOAT |
| Heating-circuit A configured mode | 1393 | UCHAR |
| Heating limit A | 1442 | UCHAR |
| Constant flow setpoint A | 1449 | UCHAR |
| Cooling limit A | 1484 | UCHAR |
| Cooling flow setpoint A | 1491 | UCHAR |
| Active heating-circuit mode A | 1498 | UCHAR |
| Parallel shift A | 1505 | UCHAR |

Circuits B-G follow the official per-circuit offsets. Do not add one to these
base addresses to manufacture a flat, non-overlapping map.

## Float encoding

IDM documents `FLOAT` as an IEEE-754 32-bit value transferred as two consecutive
16-bit Modbus registers:

1. `Reg_L` — bits 15..0
2. `Reg_H` — bits 31..16

There is no percentage scaling for humidity address 1392. Decode the two words
as a float first, then validate the physical 0-100 %RH range.

Reading address 1392 as `UCHAR` exposes only the low byte and produces apparently
random values from 0 to 255. Rejecting values above 100 after that wrong decode
only makes the entity unavailable; it does not fix the protocol error.

## Documented logical overlaps

The official tables contain logical data points whose address ranges overlap at
block boundaries. Relevant examples in the full A-G map are:

- humidity `1392 FLOAT` and heating-circuit A mode `1393 UCHAR`;
- heating curve G `1441 FLOAT` and heating limit A `1442 UCHAR`;
- cooling eco setpoint G `1483 FLOAT` and cooling limit A `1484 UCHAR`.

Treat each overlapping logical data point as a separate exact request. The
batching condition is strict adjacency without overlap:

```text
next.address == previous.address + previous.size
```

If `next.address` is lower than the expected next address, close the current
batch and begin another request. Never alter the register definition to satisfy
the batching algorithm.

## Function codes and request shape

The official documents distinguish read-only input values, read/write holding
values, and coils. Third-party working configurations also show that some IDM
values require a particular read function. Consequently:

- function code, start address, and count are part of a register's protocol
  identity;
- do not assume every readable value is interchangeable between FC03 and FC04;
- do not change function-code metadata from a community report alone;
- capture exact hardware requests before introducing firmware- or model-specific
  function-code overrides.

The `modbus_iDM_All_2025-12-21.json` audit was useful corroboration for official
heating-circuit addresses and mixed FC03/FC04 usage, but it contains no humidity
1392 entry and is therefore not primary proof for that datatype.

## Navigator 1.0/1.7 isolation

Navigator 1.0/1.7 uses a distinct map:

- TCP port 502;
- FC04 read-only input block beginning at address 1000;
- humidity sensor at `1046 FLOAT`;
- FC03/06 holding-register block beginning at address 2000;
- FC01/05 coil block beginning at address 3000;
- IEEE-754 floats use the same low-word-first ordering.

Navigator 1.0/1.7 is not currently supported by this library. Adding it requires
a separate model constant, register-map builder, detection strategy, fixtures,
tests, and hardware validation. Never merge its addresses into the existing
Navigator 2.0/10/Pro map.

## Write safety

Official IDM documentation warns that selected RW values are written to EEPROM
when changed, with a documented maximum of 300,000 writes per register. Keep
EEPROM-sensitive writes guarded and never turn them into periodic writes.
Values documented as cyclic inputs are a different class and must retain their
required refresh/TTL behavior.

Community reports corroborate that firmware revisions can add holding registers
and that write behavior can differ between installations. Those reports are
useful for identifying test targets, not for bypassing official write-safety
metadata.

## Community corroboration

- https://forum.iobroker.net/topic/22497/idm-luftw%C3%A4rmepumpe-per-modbus-anbinden-klappt-nicht-tipps
  documents real-world setup, firmware-dependent registers, EEPROM concerns,
  and intermittent connection behavior.
- https://forum.iobroker.net/topic/78083/idm-w%C3%A4rmepumpe-per-modbus-schreiben-und-lesen
  documents a Navigator 2.0 room-control setup and the difference between
  polling and explicit write impulses.

Community material is non-authoritative. Do not copy credentials, local IPs,
PINs, or private device identifiers into tests or documentation.

## Required verification for future changes

Every register-map change must verify:

- exact address, datatype, size, unit, access mode, and sentinel behavior;
- Navigator family and relevant firmware;
- exact Modbus function code, start address, and count when hardware evidence is
  available;
- grouping behavior for adjacent, gapped, and overlapping ranges;
- decoded physical value before applying range validation;
- schema snapshot and Home Assistant entity compatibility;
- EEPROM and cyclic-write safety.

Tests must model request-sensitive overlapping values where one exact request
can return a float and another overlapping request can return a different
logical UCHAR value.

## Navigator 10 unavailable-sentinel capture (2026-07-10)

A read-only hardware capture from a Navigator 10 controller verified the
following unavailable values through FC04 individual reads. The controller
returned the same raw words when the addresses were included in the API's
normal adjacent, non-overlapping batches.

| Data point | Address/count | Raw words | Decoded sentinel |
| --- | --- | --- | ---: |
| Variable input | 1006/1 | `FFFF` | `255` |
| Heating-circuit A external room temperature | 1650/2 | `0000 BF80` | `-1.0` |
| External humidity | 1692/2 | `0000 BF80` | `-1.0` |
| External groundwater pump demand M15 | 1714/1 | `FFFE` | `254` |
| External groundwater pump demand M15 SW Max | 1715/1 | `FFFE` | `254` |
| Battery state of charge | 86/1 | `FFFF` | `-1` |
| Booster fault | 4001/1 | `FFFF` | `255` |
| Humidity sensor B31 | 1392/2 | `0000 BF80` | `-1.0` |
| Cascade available for heating | 1147/1 | `FFFF` | `255` |

Twenty repeated comparisons of the initially reported five registers produced
100 identical batch/individual pairs. A broader pass covered 170 register
definitions in 45 API groups plus 144 repeated comparisons of constrained
single-word values; no raw batch/individual mismatch was observed. These
sentinels therefore represent unavailable data, not corrupt batch responses.
The cascade capability probe additionally uses the verified `255` sentinel to
avoid enabling and polling the optional cascade block on controllers that
answer address 1147 but do not implement cascade operation. A decoded value of
`0` remains a valid indication that cascade support exists but is currently
inactive.
