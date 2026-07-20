# Binary Register Metadata

`idm-heatpump-api` exposes neutral semantic metadata for binary IDM registers.
Consumers should use this catalog instead of interpreting every non-zero value
as active or deriving the meaning exclusively from the register name.

```python
from idm_heatpump import get_binary_register_metadata

metadata = get_binary_register_metadata("hp_sum_alarm")
if metadata is not None:
    print(metadata.on_values)    # (1,)
    print(metadata.off_values)   # (0,)
    print(metadata.device_class) # "problem"
```

## Fields

- `on_values`: decoded values that explicitly mean active.
- `off_values`: decoded values that explicitly mean inactive.
- `bitmask`: optional positive mask for bit-packed states.
- `inverted`: invert the decoded result for active-low signals.
- `device_class`: neutral semantic class such as `problem`, `heat`, `cold`,
  `running`, `lock`, `connectivity` or `power`.

Sentinel values declared on `RegisterDef` always take precedence. A sentinel is
not a valid active or inactive operating state and should normally be exposed as
unavailable by the consumer.

## Dynamic register names

Zone-room relay names are generated dynamically (`zm{zone}_room{room}_relay`).
`get_binary_register_metadata()` recognizes this pattern and returns the shared
`running` semantics without creating thousands of static dictionary entries.

## Compatibility

The metadata catalog is additive. Existing `RegisterDef` fields, decoding,
batch reads and writes are unchanged. Consumers can use the getter when it is
available and retain their previous fallback with older API releases.
