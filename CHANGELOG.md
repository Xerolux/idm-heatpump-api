# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]


## [0.8.6] - 2026-07-26

### Fixed

- **Modellerkennung: echtes Navigator 10 ohne konfigurierten Booster und im Standby wurde als Navigator 2.0 fehlklassifiziert (#170 live).** Die in 0.8.5 gestraffte Sentinel-Validierung für `booster_fault` (4001) schloss korrekt Terra-SWM-Navigator-2.0-Geräte aus, entzog aber auch echten Navigator-10-Anlagen ohne Booster den Ersatz-Indikator, sobald `power_limit_hp` (4108) im Standby einen unplausiblen Wert (`-1.0`/Sentinel bzw. `0.0`) lieferte. `detect_model()` zieht nun zusätzlich die Navigator-10-only-Leistungsregister `power_consumption_hp` (4122) und `thermal_power_flow_sensor` (4126) heran: Antworten **beide** Register (auch mit `0.0` im Standby), gilt das als starker, familienspezifischer Navigator-10-Nachweis. Navigator-2.0-Regelungen (inkl. IDM Terra SWM) lehnen diese Adressen mit Modbus-Ausnahmecode 2 ab, sodass die Unterscheidung sicher bleibt. Verifiziert an einer Live-Anlage mit Firmware `NAV10_20.24-880-g265e09c4a`.

### Compatibility

- Keine Änderung an `RegisterDef`, Modbus-Dekodierung, Batch-Reads, Schreibpfaden oder dem Web-Client. Lediglich `detect_model()` erhält einen zusätzlichen, strengen Tertiär-Indikator (4122 UND 4126 müssen beide antworten).
- Schließt die Lücke aus dem 0.8.5-Kompatibilitätshinweis („echtes Nav10 ohne Booster fällt auf 2.0 zurück"): ein solches Gerät wird jetzt zuverlässig als Navigator 10 erkannt, ohne die Terra-SWM-Sicherung (#44/#65) aufzuweichen.


## [0.8.5] - 2026-07-25

### Fixed

- **Modellerkennung: Navigator 2.0 mit `0xFFFF`-Antwort auf `booster_fault` (4001) wurde als Navigator 10 fehlklassifiziert.** Der in 0.8.4 eingeführte Booster-Fallback wertete **jede** 1-Register-Antwort auf Adresse 4001 als Navigator-10-Indikator — einschließlich des deklarierten „nicht konfiguriert"-Sentinels `255` (roh `0xFFFF`). Einige Navigator-2.0-Regelungen beantworten Navigator-10-only-Register jedoch mit einem Sentinel statt sie mit Modbus-Ausnahmecode 2 abzulehnen (dasselbe Terra-SWM-Verhalten, das 0.8.3 bereits für Adresse 4108 korrigierte). `detect_model()` wertet 4001 jetzt konsistent zu 4108: nur ein **nicht-sentinel** Wert (low byte ≠ 255) gilt als echter Navigator-10-Nachweis. Behebt Integration-Issue #170.

### Compatibility

- **Trade-off (bewusste Entscheidung, dokumentiert):** Ein echtes Navigator 10 **ohne** konfigurierten Booster, das 4001 mit dem Sentinel `255` beantwortet, verliert dieses Ersatz-Indikator. Die Erkennung fällt dann auf `Navigator 2.0` zurück (Registerplan ohne Nav10-only-Block), sofern Adresse 4108 keinen plausiblen Power-Limit-Wert liefert. Abfangen über (a) den primären Indikator 4108, (b) die Verbraucher-Firmware-/Web-Reconciliation (z. B. `NAV10_`-Firmware-Prefix → `set_model_info()`) oder (c) den manuellen Modell-Override in der Integration. Ein Nav 2.0 mit falscher Nav10-Klassifizierung (Nav10-only-Block wird gepollt, EEPROM-Schreibgating aktiv) ist das größere Anlagenrisiko als eine Nav10-Untererkennung, die sicher auf den 2.0-Registerplan zurückfällt.
- Keine Änderung an `RegisterDef`, Modbus-Dekodierung, Batch-Reads, Schreibpfaden oder dem Web-Client. Lediglich die 4001-Wertvalidierung in `detect_model()` ist präzisiert.


## [0.8.4] - 2026-07-22

### Fixed

- **Modellerkennung: Navigator 10 mit Standard-Power-Limit (-1.0) wurde als Navigator 2.0 fehlklassifiziert.** Wenn das Register `power_limit_hp` (Adresse 4108) den Standardwert `-1.0` ("keine Leistungsbegrenzung") liefert, prüft `detect_model()` nun zusätzlich das Booster-Register (Adresse 4001). Echtes Navigator-10-Geräte antworten auf Adresse 4001 sauber (auch ohne installierten Booster mit `0xFFFF` / Sentinel 255), während Navigator-2.0-Geräte (wie Terra SWM) Adresse 4001 mit Modbus Ausnahmecode 2 (Illegal Data Address) ablehnen.
- **`IdmHeatPumpClient.set_model_info()` hinzugefügt:** Erlaubt das explizite Setzen bzw. Überschreiben der Modellinformationen durch aufrufende Verbraucher (z.B. Home Assistant Integration oder Web-Erkennung).

### Compatibility

- Keine Änderung an `RegisterDef`, Modbus-Dekodierung, Batch-Reads, Schreibpfaden oder dem Web-Client. Lediglich die Modellauswahl in `detect_model()` ist für alle Anlagen präzisiert.


## [0.8.3] - 2026-07-22

### Fixed

- **Modellerkennung: Terra SWM / Navigator 2.0 wurde fälschlich als Navigator 10 erkannt.** Register `power_limit_hp` (Adresse 4108) wurde als Navigator-10-Indikator genutzt, wobei bereits das bloße Antworten (ohne Illegal-Address-Fehler) als Indikator gewertet wurde. Einige Navigator-2.0-Regelungen – namentlich die IDM Terra SWM – beantworten diese Adresse jedoch mit einem Sentinel-Wert (`-1.0` / `0xFFFF` oder `0.0`) anstatt sie abzulehnen. Dadurch wurde die Anlage als Navigator 10 klassifiziert, beim nachfolgenden Poll des Navigator-10-only-Registerblocks (ab 4001) korrekt mit Modbus-Ausnahmecode 2 abgelehnt und das Setup brach ab. Die Erkennung wertet jetzt nur noch plausible, konfigurierte Power-Limit-Werte (>0 kW, ≤200 kW) als Navigator-10-Indikator; Sentinel- und Nullwerte führen zur korrekten Klassifizierung als Navigator 2.0. Siehe Integration Issue #44.

### Compatibility

- Keine Änderung an `RegisterDef`, Modbus-Dekodierung, Batch-Reads, Schreibpfaden oder dem Web-Client. Lediglich die Modellauswahl in `detect_model()` ist für von der Fehlklassifizierung betroffene Anlagen korrigiert; alle anderen Installationen verhalten sich unverändert.


## [0.8.2] - 2026-07-20

### Added

- Add a Home-Assistant-independent binary register metadata catalog with explicit on/off values, optional bit masks, active-low inversion, and neutral semantic device classes.
- Add `get_binary_register_metadata()` for heating, cooling and hot-water demands, summary alarms, compressor status registers, and dynamically generated zone-room relay names.
- Export the new binary metadata types and catalog through the package-root public API.
- Document the binary metadata contract and add validation, register-map, dynamic-name, and public-API snapshot tests.

### Compatibility

- The change is additive. Existing `RegisterDef` objects, Modbus decoding, batch reads, writes, and direct Pymodbus consumers remain unchanged.

## [0.8.1] - 2026-07-19

### Fixed

- Mark zone-module room relay registers (`zm{z}_room{r}_relay`) as binary status bits. The registers keep their `UCHAR` wire type but now carry `binary=True` so downstream consumers (e.g. the Home Assistant integration) expose them as `binary_sensor` entities with `on`/`off` instead of numeric sensors showing `0`/`1`. Matches the existing library convention for UCHAR status bits (`heating_demand`, `cooling_demand`, `compressor_status_*`). Closes Xerolux/idm-heatpump-hass#128.
- Correct heating-circuit address drift in `docs/Modbus-Register.md`. Six UCHAR blocks (`hc_X_heating_limit`, `hc_X_setpoint_flow_constant`, `hc_X_cooling_limit`, `hc_X_setpoint_flow_cooling`, `hc_X_active_mode`, `hc_X_parallel_shift`) were documented at the shifted addresses introduced in 0.6.0 (e.g. `1443+idx`), even though the code had already been reverted to the original overlapping addresses that preserve the documented heating-curve-G / heating-limit-A boundary (e.g. `1442+idx`, matching `docs/Register-Map-Invariants.md` and `tests/fixtures/register_schema_v1.json`). The detailed table and the `## Heating Circuits A-G` patterns table now both match the code for all circuits A-G. Source: 2026-07-16 Navigator 10 live capture and the authoritative register map. No code change; documentation and tests only.
- Add a regression test (`tests/test_modbus_register_doc.py`) that parses the documented heating-circuit tables and locks every address against the register map built by `build_register_map`, preventing future drift.

## [0.8.0] - 2026-07-16

### Fixed

- Detect non-contiguous heating-circuit configurations (e.g. only circuits A and D installed, with B/C unconfigured) in `IdmModbusClient.detect_model()`. Heating-circuit detection no longer early-breaks after two sentinel slots and additionally probes the active operating-mode register (1498-1504) as a second presence signal, so an installed circuit that reports -1.0 on its flow-temperature register is still detected when its active-mode register confirms configuration. Source: two-device Navigator 10 capture (2026-07-16).
- Expose heating-circuit flow temperature, pump, and mixer for circuits B-G in the Navigator 10 web client. Previously only HK A and HK C were mapped; HK D (and B/E/F/G) were silently dropped even when the controller reported them. Mappings follow the verified linear raw-key sequences B51+i (flow temperature), M31+i (pump), and M41+i (mixer); B54/M34/M44 for circuit D confirmed live on a Navigator 10 ALM with circuits A+D (2026-07-16).

## [0.7.7] - 2026-07-16

### Fixed

- Stabilize Navigator 2.0 local web logins for direct IPv4/IPv6 hosts by allowing aiohttp to accept cookies from IP literals when the API creates its own HTTP session.

## [0.7.6] - 2026-07-11

### Fixed

- Propagate exhausted transport and no-response failures from grouped and
  individual fallback reads instead of treating them as register-specific
  errors and potentially disabling otherwise valid registers.
- Treat the hardware-verified value `255` at cascade capability register 1147
  as unavailable during model detection instead of enabling an unsupported
  cascade register block.

### Added

- Allow consumers to quarantine device-specific registers from grouped reads
  after an external plausibility check detects a valid-looking but wrong batch
  value.
- Add an explicit `allow_custom_register` escape hatch for advanced raw writes.
  It bypasses only detected-model map membership while retaining datatype,
  numeric and write-metadata validation.

## [0.7.5] - 2026-07-10

### Fixed

- Mark the hardware-verified unavailable values for variable input, battery
  state of charge, booster fault, external humidity, external room
  temperatures, humidity sensor B31 and external groundwater-pump demands as
  register sentinels. They are no longer quarantined, re-read individually and
  warned about on every polling cycle as if they were corrupt batch values.

### Tests

- Record the anonymized Navigator 10 FC04 hardware capture and regression-test
  the sentinel metadata used by batch validation.

## [0.7.4] - 2026-07-10

### Fixed

- Restore the official Navigator 2.0/10 heating-circuit addresses and decode
  `humidity_sensor` at address 1392 as a two-register IEEE-754 float. The
  previous overlap-normalization changed documented addresses and exposed the
  humidity float's low byte as a 0-255 percentage value.
- Split overlapping logical register ranges into separate Modbus requests so
  each IDM data point is read with its documented start address and size.
- Treat pymodbus `ModbusIOException` no-response failures as connection
  failures: close the potentially stale TCP socket, reconnect, and retry the
  interrupted request instead of repeatedly using the same dead session.

### Documentation

- Add mandatory agent guidance and a source-backed register-map invariants
  reference covering Navigator 1.x isolation, Navigator 2.0/10 overlaps,
  encoding, batching, function-code evidence, and write safety.

## [0.7.3] - 2026-07-10

### Fixed

- Do not report unconfigured Navigator heating-circuit slots as active when
  their responding flow-temperature register contains the documented `-1.0`
  unavailable sentinel.

## [0.7.2] - 2026-07-10

### Fixed

- Stop grouped Modbus reads from spanning unrequested address gaps, quarantine
  registers whose batch values violate their declared range or enum metadata,
  and validate the individual recovery value before exposing it.
- Define the physical 0-100 % range for `humidity_sensor`, preventing corrupt
  batch values from reaching consumers.

### Added

- Expose batch-quarantined register names through client diagnostics and
  `get_batch_unsafe_registers()`.

## [0.7.1] - 2026-07-09

### Security

- Validate local web client hosts before constructing HTTP or WebSocket URLs,
  preventing URL-authority injection and unintended PIN disclosure.
- Run release validation with read-only GitHub permissions, remove unnecessary
  OIDC access, and expose write credentials only during the final push step.

### Fixed

- Reject unsupported enum values, ambiguous boolean inputs, non-finite values,
  and fractional values for integer Modbus registers before writes are sent.
- Reset transient Modbus failure counters after a successful individual read so
  intermittent errors cannot permanently disable a working register.
- Reject malformed Navigator 10 authorization payloads without leaking the
  WebSocket and reject Navigator 2.0 JSON authentication errors as data.
- Validate manual heating-circuit identifiers as exactly one letter from A-G.
- Normalize repository text files to LF and enforce LF through `.gitattributes`.

### Changed

- Reuse freshly probed Navigator 2.0 endpoint responses for the initial data
  snapshot, avoiding duplicate HTTP requests during startup.

### Tests

- Add regression coverage for host validation, IPv6 URL formatting, malformed
  authentication payloads, safe Modbus writes, failure-counter recovery,
  heating-circuit validation, and Navigator 2.0 probe reuse.

## [0.7.0] - 2026-07-09

### Added

- Add the documented `IdmModbusClient.get_unsupported_registers()` query for
  consumers that maintain a polling skip-list. It reports only registers
  explicitly rejected by the controller with Modbus exception code 2.

## [0.6.5] - 2026-07-09

### Changed

- Refresh release metadata after 0.6.4.

## [0.6.4] - 2026-07-09

### Changed

- Optimize the Navigator 10 web client request path: the recoverable- and
  reconnect-error tuples are now built once at module import instead of being
  reconstructed on every websocket request.
- Parse the Navigator 10 authorization response only once during connect (new
  `_parse_auth_response` helper) instead of decoding the same frame twice.
- Remove a redundant second normalization of the lookup key in
  `parse_idm_html_table_values`.
- Make the Navigator 2.0 `read_data` path filter explicit and self-documenting
  (`selected_paths`).

### Fixed

- Harden `IdmNavigator20WebClient.close()` so a failing `session.close()`
  cannot leak the session reference or leave detected endpoints and the CSRF
  token behind. It now matches the defensive close behavior of the Navigator 10
  client.

### Tests

- Add coverage for `IdmNavigator10WebClient.read_statistics` (previously 0%).
- Add coverage for Navigator 2.0 `capabilities()` and `diagnostics()`.
- Add constructor-validation tests for both web clients.
- Add `__aenter__`/`__aexit__` context-manager tests for both web clients.
- Add a Navigator 2.0 close test that fails the underlying session close.

## [0.6.3] - 2026-07-07

### Fixed

- Treat `TimeoutError` (including `asyncio.TimeoutError`) as a retryable
  transport error in `IdmModbusClient`. Previously a slow or unresponsive
  controller that timed out bypassed the retry/reconnect loop.
- Make `read_register()` respect the permanently-failed register set, matching
  the behavior of `read_batch()`. This avoids repeated futile network requests
  for registers already known to be unavailable.
- Close the Navigator 10 websocket and session defensively so a failing
  `close()` no longer leaks the websocket reference or session state.
- Correct the `detect_model()` docstring to match the actual probing strategy.

### Changed

- Optimize `read_batch()` grouping: registers are now sorted once by
  `(register_type, address)` and grouped in a single pass, removing the
  previous input/holding split and second sort.

## [0.6.2] - 2026-07-06

### Fixed

- Support older IDM zone modules with up to 8 rooms by allowing
  `get_zone_module_registers()` and `build_register_map()` to generate room 7
  and room 8 registers (issue Xerolux/idm-heatpump-hass#68).
- Recover corrupt enum/UCHAR values returned by some controllers in large batch
  reads by re-reading out-of-range values individually. This fixes room-mode
  registers that appeared as invalid values such as 196 or 255 in Home Assistant
  even though single reads returned the correct values (issue
  Xerolux/idm-heatpump-hass#69).

## [0.6.1] - 2026-07-06

### Added

- Add an LRU cache to `build_register_map()` so repeated map builds for the same
  model or manual configuration are essentially free.
- Add an O(1) address index to `RegisterRegistry` for faster `by_address()`
  lookups.
- Add a unified `_retry_command()` helper in `IdmModbusClient` that handles
  retries, backoff, reconnect, and error-context recording for both reads and
  writes.

### Changed

- Replace the long `if/elif` chains in `IdmModbusClient.decode_value()` and
  `encode_value()` with dispatch tables; decoding/encoding is now faster and
  easier to extend.
- Make `IdmModbusClient.disconnect()` acquire the client lock before closing the
  underlying transport, preventing races with in-flight reads/writes.
- Cache aiohttp WebSocket message-type constants and `aiohttp.ClientError` at
  module import time to avoid repeated conditional imports on every web request.
- Tighten exception handling in Navigator 2.0 login and endpoint probing so only
  expected transport/protocol errors are swallowed.

### Fixed

- Fix the redundant HTTP status check in `IdmNavigator20WebClient._request_text()`
  so `require_ok=False` actually allows non-200 responses (used during login
  fallbacks and endpoint probing).
- Fix Navigator 2.0 login logic so empty/bad responses no longer abort the
  login-path loop prematurely, while successful non-login responses still end
  the loop as expected.
- Remove unused `CYCLIC_REGISTERS` constant from `idm_heatpump.const`.
- Improve Navigator 2.0 login robustness:
  - do not send a possibly stale CSRF token in the login POST itself;
  - send the CSRF token under three common header names
    (`CSRF-Token`, `X-CSRF-Token`, `X-CSRFToken`);
  - automatically re-login once when a data endpoint rejects the CSRF token;
  - tighten login-page detection by looking for a `<form>` with a
    password/PIN input field;
  - add debug logging for every login step and endpoint probe.
- Deduplicate FLOAT32 decoding in `detect_model()` with a new
  `_probe_float_value()` helper.
- Add per-attempt debug/warning logging to the Modbus retry loop.
- Make `mypy` strict clean for the entire test suite.
- Add `tests/test_performance.py` with sanity checks for register-map caching
  and `read_batch()` grouping efficiency.
- Add configurable `max_group_size` parameter to `IdmModbusClient` (default 40)
  so consumers can tune the batch-read chunk size for controllers that return
  inconsistent data in large contiguous reads.
- Add post-batch validation in `_read_group()`: after a successful batch read,
  any register whose decoded value falls outside its declared `enum_options` or
  `min_val`/`max_val` range is automatically re-read individually. This fixes
  corrupt UCHAR values (e.g. zone-module room-mode registers showing 255/196
  instead of 0–4) returned by some IDM controllers during large batch reads
  (issue #69).

### Changed

- Increase `MAX_ROOMS_PER_ZONE` from 6 to 8 so that older IDM zone modules with
  up to 8 rooms per module are supported. `get_zone_module_registers()` and
  `build_register_map()` now accept `room_count`/`rooms_per_zone` values of 1–8
  (issue #68).

## [0.6.0] - 2026-07-05

### Added

- Add optional `pymodbus_retries` parameter to `IdmModbusClient` (default `0`)
  so consumers can control pymodbus-internal retries independently of the
  library's own retry loop.
- Add public `quiet_pymodbus_logging()` helper to mute pymodbus frame-level
  logging (`>>>>> send/recv`, `Cancel send, because not connected!`) that floods
  Home Assistant logs on unstable TCP links.
- Add a real Troubleshooting section to the docs covering connection drops and
  pymodbus log noise.
- Add validation to `build_register_map()` for `circuits`, `zone_modules`, and
  `rooms_per_zone`.
- Add address-overlap and full-map lookup tests for the register definitions.

### Changed

- Disable pymodbus-internal retries by default. The library already implements
  its own retry loop with exponential backoff in `_read_registers` /
  `_write_registers`. Stacking pymodbus's internal retries (previously `3`)
  multiplied the effective attempt count (up to 9 attempts per register) and
  produced noisy "No response received after N retries" log lines on every
  failure. pymodbus now returns failures immediately and the library handles
  retries cleanly.
- Configure `AsyncModbusTcpClient` with explicit `reconnect_delay` (0.5s) and
  `reconnect_delay_max` (10s) for faster, more predictable reconnect behavior.
- `get_register()` and `get_all_registers()` now accept an optional
  `model_info` keyword argument and search the full register map when provided,
  instead of only the small legacy core set.
- `detect_model()` now treats a successful read of cascade register 1147 as
  cascade presence, regardless of the value (0 can mean "present but inactive").
- Cache the register map built from detected model info in `IdmModbusClient`,
  avoiding repeated rebuilds on every write validation.

### Fixed

- Correct heating-circuit register addresses that overlapped when all 7 circuits
  (A-G) were enabled:
  - `hc_X_heating_limit` shifted from 1442+idx to 1443+idx.
  - `hc_X_setpoint_flow_constant` shifted from 1449+idx to 1450+idx.
  - `hc_X_cooling_limit` shifted from 1484+idx to 1485+idx.
  - `hc_X_setpoint_flow_cooling` shifted from 1491+idx to 1492+idx.
  - `hc_X_active_mode` shifted from 1498+idx to 1499+idx.
  - `hc_X_parallel_shift` shifted from 1505+idx to 1506+idx.
  - `humidity_sensor` changed from FLOAT (2 registers) to UCHAR (1 register) at
    address 1392 to avoid overlapping `hc_a_mode` at 1393.
- Fix Navigator 10 web client session leaks when `connect()` or
  `_send_json_and_receive_text()` fails.
- Add `asyncio.Lock` to Navigator 10/2.0 web clients to prevent race conditions
  and request/response interleaving on concurrent connect/read calls.
- Parse Navigator 10 authorization response as JSON instead of fragile string
  matching, so pretty-printed or formatted responses are accepted.
- Treat `aiohttp.ClientError` as a retryable transport error in the Navigator 10
  web client.
- Do not retry `IdmWebAuthenticationError` in the Navigator 10 web client.
- Explicitly handle `WSMsgType.CLOSED` frames in the Navigator 10 web client.
- Treat HTTP 401/403 on Navigator 2.0 login as authentication failures.
- Validate that Navigator 2.0 login returns a non-empty CSRF token and clear it
  on `close()` so a reopened client does not reuse stale credentials.
- URL-encode the Navigator 10 PIN in the WebSocket query string.
- Avoid an unnecessary inter-request sleep after the last Navigator 10 setting
  request.
- Prevent `__aexit__` from masking the original exception if `close()` raises.
- Stop treating Modbus address 1072 (heat-sink flow rate) as a Navigator 10
  indicator during model detection. Some Navigator 2.0 controllers (e.g. IDM
  Terra SWM with software 20.23-245) expose this register and were
  misclassified as Navigator 10. Detection now relies on address 4108
  (power-limit register), which is Navigator-10-only.

## [0.5.1] - 2026-07-05

### Fixed

- Fix `detect_model()` no longer classifies Navigator 2.0 controllers as
  Navigator 10 just because address 1072 (`heat_sink_flow_rate`) responds.
  That address is also present on some Navigator 2.0 devices (e.g. IDM Terra SWM
  with software 20.23-245). Navigator-10 detection now relies on address 4108
  (`power_limit_hp`), which is part of the Navigator-10-only power-limitation
  register block. This closes the root cause behind the first-setup failures
  reported in the Home Assistant integration issue #44.


## [0.5.0] - 2026-07-04

### Added

- Add stable metadata for known local web values via `WEB_VALUE_DESCRIPTIONS`
  and `IdmWebValueDescription`, plus `IdmWebData.get_value()` and
  `IdmWebData.get_numeric()` helpers for consumers.
- Add `RECOMMENDED_WEB_SCAN_INTERVAL` for Home Assistant-style web supplement
  polling defaults.
- Add `detect_model(read_firmware=False)` for consumers that prefer the local
  web software version or want to avoid probing unreliable Modbus register 4120.

### Fixed

- Let injected Navigator 10 web test sessions run without importing `aiohttp`,
  keeping optional dependency behavior easier to verify locally.
- Reconnect the Navigator 10 WebSocket once when a stale or closed connection is
  detected during a web supplement request.

## [0.4.1] - 2026-07-03

### Fixed

- Speed up automatic model and capability detection by using short, single-attempt
  Modbus probes for optional model registers. Normal polling keeps the existing
  robust timeout and retry defaults.
- Stop probing contiguous optional heating-circuit and zone-module slots after
  repeated empty responses, reducing detection time on smaller systems and proxies.
- Retry transport-level `OSError`/timeout failures through the reconnect path instead
  of letting transient socket errors bypass the normal retry handling.
- Reduce the default Navigator 10 web inter-request delay from 0.3s to 0.05s and
  make it configurable through `request_delay`, improving 30s web polling latency
  while keeping gentle pacing available.

## [0.4.0] - 2026-07-03

### Added

- Add an optional read-only local web supplement for Navigator 10 and Navigator 2.0.
  Navigator 10 uses the local WebSocket interface and Navigator 2.0 uses the local
  HTTP interface with CSRF handling.
- Expose web supplement data for values that are missing or incomplete in Modbus,
  including software version, flow rate, hot gas temperature, pressure values,
  board and battery voltage, additional hot-water station values, runtime counters,
  heat quantities, and infosystem notifications.
- Add optional web-client factories that return `None` when no local network PIN is
  configured so consumers can keep Modbus-only operation error-free.

### Changed

- Keep the Modbus `firmware_version` register available but disable it by default,
  because some Navigator 10 firmware builds reject register 4120 while the same
  software version is available through the local web interface.

## [0.3.7] - 2026-07-02

### Fixed

- Exclude Navigator 10-only register blocks, including power limit register 4108, when
  `build_register_map()` receives detected Navigator 2.0, Navigator Pro, or unknown model data.

## [0.3.6] - 2026-07-02

### Fixed

- Reject invalid register data types, register types, scaling multipliers, and value bounds
  when register metadata is created, instead of failing later during device I/O.
- Reject incomplete Modbus responses and ignore malformed capability probes during automatic
  model detection.
- Restore the GitHub bug-report template, which accidentally contained funding configuration.

## [0.3.5] - 2026-06-23

### Added

- Added firmware-version detection to `detect_model()` results.
- Added the `model_name` convenience property with the Navigator 2.0 fallback for
  unknown or not-yet-detected models.

### Changed

- Improved automatic heat-pump model detection coverage.

## [0.3.4] - 2026-06-22

### Fixed

- Fixed package tool configuration for Ruff and mypy.
- Hardened CI and removed dead code around model/register handling.

## [0.3.3] - 2026-06-18

### Fixed

- Fixed model-detection feature handling.

## [0.3.2] - 2026-06

All register definitions were verified line by line against the official iDM
"Montageanleitung MODBUS TCP NAVIGATOR 10" (Stand 18.06.2025).

### Fixed

- **Zone modules: corrected room register stride from 8 to 7.** Room blocks are 7
  registers wide (e.g. zone module 1, room 2 starts at 2009, not 2010). All room
  addresses for rooms 2-6 were previously wrong.
- **`smart_grid_status` moved from address 1006 to address 90** with the correct
  Navigator 10 enum (0=Red, 1=Yellow, 2=Green, 4=Supergreen). Address 1006 is the
  variable input ("Variabler Eingang") and is now exposed as `variable_input`.
- **`battery_soc` (86): changed from `FLOAT` to `INT16`** — the official doc lists it
  as WORD (single register, -1 = unavailable). As FLOAT it read two registers and
  decoded garbage.
- **`internal_message` (1004): changed from `UCHAR` to `UINT16`** — message numbers
  range from 020 to 999 and were corrupted by the one-byte mask.
- **Pump status registers (1074, 1104, 1105, 1106, 1108, 1109) and booster pumps
  (4020, 4021, 4050, 4051): changed from `UINT16` to `INT16`** — these report -1 for
  "off", which previously decoded as 65535 %.
- **`isc_mode` (1874) is read-only again** — the official doc lists it as RO
  (writability was incorrectly introduced in 0.3.0).
- **`ext_demand_groundwater_pump_m15` (1714) / 1715: changed from `UINT16` to `UCHAR`**
  with range 0-100 per the official doc. Renamed `ext_demand_brine_pump_m16` to
  `ext_demand_groundwater_pump_m15_sw_max` — address 1715 controls the groundwater
  pump M15 on SW Max, not the brine pump M16.
- **`heat_source_pump_status` (1106): added missing `%` unit and state_class.**
- **`pyproject.toml`: fixed broken tool configs** — `ruff.target-version` and
  `mypy.python_version` contained the package version ("0.3.1") instead of
  "py312" / "3.12".
- `client.py`: heating-circuit detection now adds the `FEATURE_HEATING_CIRCUITS`
  constant instead of a hard-coded string, and `HEATING_CIRCUIT_LETTERS` is imported
  from `const` instead of being redefined.

### Added

- `pv_target_value` register (address 88, FLOAT, kW) — PV target value for
  Smartfox / Solar-Log.
- `VARIABLE_INPUT_OPTIONS` and `EVU_LOCK_OPTIONS` enums (exported from the package).
- `evu_lock` (1098) now has enum options (0=Locked, 1=Not Locked).
- Write limits per official doc: bivalence points 1120-1123 and cascade bivalence
  points 1226-1231 (-40..40 °C), `system_mode` (0..5), zone-module room modes (0..4).
- PV registers 74-88 are now writable (RW/RO per official doc — a building management
  system writes these values to the heat pump).
- Zone-module room temperature and humidity registers are now writable (RW/RO — RW
  when external/GLT room sensors are used), with documented ranges (15-30 °C / 0-100 %).
- `current_electricity_price` (1048) now has its documented unit (€/MWh).
- Address-accuracy tests for heating circuits, zone modules and PV registers.

### Changed

- `get_zone_module_registers` now accepts at most 6 rooms (matching the official
  register map; rooms beyond 6 would produce undocumented addresses).
- `HP_OPERATING_MODE_OPTIONS`: value 0 renamed from "Off" to "Standby" per official doc.
- `docs/Modbus-Register.md` regenerated as a verified register reference (it previously
  contained unrelated contributing guidelines).

## [0.3.1] - 2026-06-02

### Changed

- Added the first 0.3.x release-flow metadata updates after the package rename.

## [0.3.0] - 2026-06

### Breaking

- PyPI package renamed from `idm-heatpump` to `idm-heatpump-api`. Install with `pip install idm-heatpump-api`. Python import remains `from idm_heatpump import ...`.

### Added

- New `RegisterDef` metadata fields for better Home Assistant integration support:
  - `binary: bool` — mark registers as binary sensors (e.g. compressor status, alarms)
  - `enabled_by_default: bool` — control default entity visibility in HA
  - `state_class: str | None` — HA state class ("measurement", "total", "total_increasing")
  - `icon: str | None` — default icon for HA entities
  - `write_only: bool` — mark write-only registers (e.g. error_acknowledge)
  - `exclude_from_write: set[int] | None` — exclude enum values from being written (e.g. 255)
- 8 registers now marked as `binary=True`: `hp_sum_alarm`, `compressor_status_1-4`, `heating_demand`, `cooling_demand`, `dhw_demand`
- `isc_mode` (address 1874) is now writable with `exclude_from_write={255}`
- `exclude_from_write={255}` added to all heating circuit mode registers (`hc_X_mode`)
- Funding badges and support section in README

### Fixed

- `battery_soc` (address 86): changed from `UINT16` to `FLOAT` to match actual device encoding
- `firmware_version` (address 4120): changed from `UINT16` to `FLOAT` (all surrounding registers are FLOAT)
- `error_acknowledge` (address 1999): now correctly marked as `write_only=True` — read attempts will raise instead of failing silently
- `read_register()` and `read_batch()` now properly skip write-only registers
- `write_register()` now validates `exclude_from_write` values before sending to device
- Removed unused `RegisterType` import from `registers.py`

## [0.2.2] - 2026-05

### Changed

- Historical release without a dedicated changelog entry before changelog
  continuity checks were added.

## [0.2.1] - 2026-05

### Fixes

- Added support for value 255 ("Not configured / Unavailable") in `ISC_MODE_OPTIONS`, `ACTIVE_HC_MODE_OPTIONS`, and `CIRCUIT_MODE_OPTIONS`.
- Added `firmware_version` register (address 4120) to the default register map.
- Improved logging for `firmware_version`: now logs at debug level instead of warning when it permanently fails (common on some Navigator 10 firmwares).
- Minor improvements for better compatibility with real Navigator 10 devices.

## [0.2.0] - 2026-05

### Breaking / Important

- Restructured package for clean PyPI distribution (`import idm_heatpump`).
- The library is now the shared Modbus/register core for the Home Assistant custom integration (migration Option B).

### Features

- Full Navigator 10 support (heat sink flow rate 1072, boosters, power limitation, etc.).
- Improved model detection for Navigator 10.

### Packaging

- Added proper release workflow for PyPI (modeled after violet-poolController-api).
- Clean top-level package layout.
