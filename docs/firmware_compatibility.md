# Firmware Compatibility Matrix

This matrix documents known Navigator generations and the preferred detection strategy. It is intentionally conservative: capability probes and verified endpoints should take precedence over model names whenever possible.

| Firmware / software | Navigator generation | Supported status | Notes |
| --- | --- | --- | --- |
| 4.x / legacy | Navigator 2.0 | Supported | Prefer HTTP capability detection with session cookies and available `/data/*.php` endpoints. |
| 5.x | Navigator 10 / Pro | Supported | Prefer local WebSocket capability detection on port `61220`, then Modbus capability probes. |
| 6.x and newer | Navigator 10 / future | Unknown / expected compatible | Treat as capability-driven until real anonymized golden data is added. |
| Unknown | Unknown | Probe only | Avoid model-name assumptions; use Modbus register probes and optional web diagnostics. |

## Golden data policy

Anonymized firmware samples should be stored under:

- `tests/data/nav2/`
- `tests/data/nav10/`
- `tests/data/navpro/`

Do not commit PINs, cookies, CSRF tokens, serial numbers, email addresses, or customer-specific network data.
