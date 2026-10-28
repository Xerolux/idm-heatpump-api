# Navigator 2.0 structured JSON responses

A voluntarily donated capture reviewed privately on 2026-10-28 exposed a second
response shape on the existing read-only Navigator 2.0 endpoints. The public
regressions are synthetic: they preserve the protocol structure, not the
submitter's names, credentials, identifiers, timestamps, schedules or readings.
The original submission remains subject to its stated retention policy.

`heatpump.php` returns objects for `system`, `freshwater`, `hk`, `pv` and
`circulation`, rather than an HTML value table. The archived frontend shows
`system.temperatures.hpout` as outgoing heat-pump water and `hpin` as incoming
water, in Celsius. The known `hk` circuit identifier selects the existing flow
and room-temperature sensor names; custom display names are not used. `info.php`
exposes the outdoor temperature as `out`.

The patch maps these proven temperature paths to existing sensor names. It does
not infer DHW top/bottom positions, source-medium type, state enumerations, PV
sign conventions or undocumented register definitions from the shape alone.
Missing, malformed, nonfinite and boolean readings are omitted, not replaced
with zero. Duplicate circuit IDs are ambiguous and omitted.

Statistics version 2 nests the existing `unitTotal` and category `total` list in
`data`; it uses the same runtime/energy units and localized category names as
the flat format. Both layouts keep the existing normalized keys and scaling.
This change is in the device library; consumers must install a released library
version containing it before claiming runtime support.
