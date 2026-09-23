# IDM Navigator protocol analysis

This document records confirmed observations from static analysis of the
Navigator desktop client and a read-only validation against a Navigator 10
controller. It is an engineering reference, not a complete protocol
specification.

## Confirmed local paths

The validated Navigator 10 installation exposes:

- Modbus TCP on port `502`, unit/slave ID `1`.
- An HTTP frontend on port `80`.
- A local WebSocket backend on port `61220`.
- Navigator 10 WebSocket authentication through the `auth_code` query
  parameter.
- Read-only setting requests returning typed values with units and translated
  text.

The local WebSocket client in `idm_heatpump.web` is therefore the supported
implementation path. It must remain read-only and must not be replaced by a
cloud dependency.

## Validated controller snapshot

The controller used for validation was identified as `Navigator 10`. The
library detected no zone modules and detected only heating circuit `A` after
the unavailable `-1.0` flow-temperature sentinel was handled correctly.

The local web interface returned 60 normalized values, including temperatures,
pressures, energy/runtime counters, statuses, software version and a
redacted myIDM identifier. No account identifier, PIN, IP address or raw
payload is stored in this repository.

## Navigator 10 WebSocket home screen (validated September 2026)

The Navigator 10 web interface renders the display's demand reason
("Anforderungsgrund") from the `home/detail` WebSocket frame. The frame is a
widget tree (envelope `home` for the full push, `homeDetail` for a detail
request); every demand-reason widget carries `operationMode` and — only while
a demand is active — an `info` bitmask. `operationMode` selects the table:
`1` heating, `4` domestic hot water, `0` "no information", `8` "off". The
decode priority and bit assignment below reproduce the web UI's JavaScript
(firmware jsonVersion 11) and were confirmed against live frames.

**Heating reasons (`operationMode` 1), in priority order:**

| Bit | Reason slug |
|-----|-------------|
| 2 | `no_info` |
| 4 | `external_input` |
| 8 | `external_bus` |
| 16 | `isc` |
| **32** | **`pv`** |
| 64 | `frost_protection` |
| 128–8192 | `hc_a` … `hc_g` |
| 16384 | `system_off` |
| 32768 | `ion` |

**Domestic hot water reasons (`operationMode` 4), in priority order:**

| Bit | Reason slug |
|-----|-------------|
| 2 | `single_loading` |
| 4 | `single_loading_boost` |
| 8 | `external_input` |
| 16 | `external_bus` |
| **32** | **`pv`** |
| 64 | `isc` |
| 128 | `schedule` |
| 256 | `schedule_boost` |
| 512 | `system_off` |
| 1024 | `dhw_comfort` |
| 2048 | `ion` |
| 4096 | `cascade` |
| 8192 | `dhw_booster` |

More than one set bit (ignoring bit 0) decodes as `more_demands`. The
energy-flow widget carries the live `pv`/`grid` power values as strings.
The library exposes all of this through `IdmNavigator10WebClient.read_home_detail()`
(`IdmWebHomeDetail`, `IdmWebDemandReason`, `decode_navigator10_demand_reason()`,
`parse_navigator_home_response()`).

## Static-analysis findings

The Navigator client contains support for multiple generations:

- Navigator 1.0/1.7 and Pro: UDP discovery and legacy UDP communication.
- Navigator 2.0: TCP/TLS communication and `NC_CHANNELDATA` live events.
- Shared concepts: channels, parameters, rooms, errors, translations,
  virtual channels and historical MAL/CSV data.

Observed data type names include `UDP_SENSOR`, `UDP_FLOAT`, `UDP_FUNCFLOAT`,
`UDP_SPECIALFLOAT`, `UDP_SLONG`, `UDP_FUNCSLONG`, `UDP_BYTE`, `UDP_FUNCBYTE`,
`UDP_USINT` and `UDP_DATETIME`. Their complete byte order, scaling and
semantics are not established by this analysis.

## Cloud boundary

Static analysis found myIDM cloud hosts, login/session handling, token status,
heat-pump lists, permissions and dynamic channel metadata. These observations
are not sufficient to implement a stable cloud client and contain sensitive
account/plant data. The library and Home Assistant integration intentionally do
not implement that cloud path.

## Not implemented by design

The following remain outside the read-only scope:

- firmware/configuration uploads and SD-card writes;
- register writes that are not already covered by the documented Modbus API;
- cloud login, cloud polling and cloud plant management;
- guessing channel meanings, units or scaling factors from EXE strings alone;
- fixed UDP ports or undocumented binary packet formats.

## Evidence still needed

Future protocol work requires anonymized local captures or exports containing
channel IDs, names, units, scaling, data types, room mappings and live event
frames. Any capture must remove PINs, tokens, IP addresses, serial numbers,
account identifiers and owner/contact data before being committed.
