## Plan: Kaleido BLE Protocol Compliance Test Suite

**TL;DR:** A `pytest` suite that connects to the ZephyrOS simulator via real BLE (`bleak`), then verifies every aspect of the Kaleido protocol spec section by section. Tests are async, ordered, and grouped 1:1 with the manual's chapters.

---

### Directory structure

```
tests/
  conftest.py                    — BLE session fixture, --device-address CLI option
  pyproject.toml                 — asyncio_mode="auto", markers
  helpers/
    __init__.py
    constants.py                 — All UUIDs, unlock token, enum values, limits
    codec.py                     — Wire encode/decode pure functions
    ble.py                       — Notify-collect helper, notification waiter
  test_s04_characteristics.py    — §4
  test_s05_connection_state.py   — §5
  test_s06_wire_conventions.py   — §6
  test_s07_command_protocol.py   — §7
  test_s08_write_operations.py   — §8 (all 16 ops)
  test_s09_read_operations.py    — §9 (all 12 reads)
  test_s10_notifications.py      — §10
  test_s11_enumerations.py       — §11
  test_s12_data_models.py        — §12
  test_s13_alarm_system.py       — §13
  test_s14_security.py           — §14
  test_s15_sequences.py          — §15 (9 sequences)
  test_s16_unit_conversions.py   — §16
  test_s17_alert_thresholds.py   — §17
  test_s18_error_handling.py     — §18
```

---

### Steps

**Phase 1 — Scaffolding** *(no BLE needed, pure setup)*

1. Create `pyproject.toml` with `asyncio_mode = "auto"`, `timeout = 10`, `markers = ["slow", "sequence"]`
2. Create `helpers/constants.py` — all UUIDs (`SERVICE_UUID`, `CHAR_*` names), `UNLOCK_TOKEN`, enum dicts, operational limits from §3
3. Create `helpers/codec.py` — pure encode/decode functions:
   - `encode_bolus(pulses: int) → bytes` (6 bytes, §8.1)
   - `encode_temp_basal(pct: int, duration_min: int) → bytes` (4 bytes, §8.2)
   - `encode_system_time(dt, tci, roc) → bytes` (9 bytes, §8.3)
   - `encode_basal_profile(rates: list[float]) → bytes` (44 bytes, §8.4)
   - `encode_command(cmd_id: int, payload: bytes) → bytes` (§7)
   - `encode_alarm_ack(bit_indices: list[int]) → bytes` (18 bytes, §8.8)
   - `decode_alarm_bitfield(data: bytes) → list[int]` (20 bytes → active bit indices, §13)
   - `pulses_to_units(p: int) → float` and `units_to_pulses(u: float) → int` (§16)
4. Create `helpers/ble.py` — `notify_and_collect(client, char_uuid, action_coro, timeout=5.0)` helper that subscribes, runs action, collects the first matching notification
5. Create `conftest.py` with:
   - `pytest_addoption`: `--device-address` (required), `--device-name` (alternative)
   - `ble_client` — **session-scoped** async fixture: `BleakClient(address)`, connect once, disconnect at teardown
   - `unlocked_client` — session fixture: calls `ble_client` + sends unlock sequence (§14.2), provides ready-to-use client
   - `reset_state` — function-scoped fixture: calls `updateDelivery(STOPPED)` to return to a clean state

**Phase 2 — Protocol unit tests** *(can run without BLE by mocking codec functions)*

6. **`test_s06_wire_conventions.py`** — Verify codec helpers encode correctly:
   - Bolus `1.0 U` → `[0x14, 0x00, 0x00, 0x00, 0x00, 0x00]`
   - Temp basal `100% / 30 min` → `[0x64, 0x00, 0x1E, 0x00]`
   - System time `2026-04-18 12:30:00, tci=1, roc=0` → exact 9-byte sequence
   - Basal profile `[1.0 U/hr × 24]` → byte 20 = `0x14` repeated
   - Ring command → `[0x03, 0x0F, 0x07, ...]` exact 17-byte match
   - Unlock command → `[0x05, 0x4F, 0x54, ...]` exact 17-byte match

7. **`test_s11_enumerations.py`** — Parameterize all enum values:
   - `KldIduMode`: BOOT=0 … SHUTDOWN=4
   - `KldDeliveryState`: UNDEFINED=0 … DELIVERING=4
   - `KldDeliveryType` bitmask: `0x01`=basal, `0x02`=temp, `0x04`=bolus, `0x05`=basal+bolus
   - `ConnectionState`: all 8 values

8. **`test_s16_unit_conversions.py`** — Parameterized pulse/unit table (§16 examples: 10→0.5 U, 400→20.0 U, etc.), rounding, basal byte encoding `rate_byte = round(rate / 0.05)`

9. **`test_s12_data_models.py`** — Round-trip encode/decode for each model class: `KldSystemTime`, `ReservoirLevel`, `KldBasalProfile`, `KldPumpBolusRequest`, `KldTemporaryBasalRequest`

**Phase 3 — BLE characteristic tests** *(requires device)*

10. **`test_s04_characteristics.py`** — Connect, discover services, verify all 20 characteristic UUIDs are present (Appendix A), verify service UUID prefix `812321XX`

11. **`test_s05_connection_state.py`** — Test each state transition:
    - Disconnect → Connect reaches `CONNECTED_AVAILABLE`
    - Unlock transitions `PENDING_UNLOCK → CONNECTED_AVAILABLE`
    - Disconnect from connected state → `DISCONNECTED`

12. **`test_s07_command_protocol.py`** — Write each command packet to `0x2118` and verify pump accepts (no error notification), includes: StorePairingKey, ClearPairingKey, Ring, UnlockPump

13. **`test_s08_write_operations.py`** — One test per write operation (§8.1–§8.16), each writes the characteristic and verifies either a read-back or a notification matches. Parameterize bolus amounts and temp basal percentages.

14. **`test_s09_read_operations.py`** — Read each readable characteristic (12 ops), assert correct data size and valid enum value. E.g., `readDeliveryState` → 1 byte, value in `[0,1,2,3,4]`.

15. **`test_s10_notifications.py`** — Trigger a state change, assert the notification arrives on the correct characteristic UUID, assert correct `DATA_SIZE`, assert valid parsed value. Tests `ParsingFailureMessage` path by sending wrong-length data (if the simulator supports a test injection mode).

16. **`test_s13_alarm_system.py`** — Alarm bitfield encode/decode with all 74 known bit indices (parametrized), acknowledgment round-trip, inverted-bit logic (0 = active), `+6` offset.

17. **`test_s14_security.py`** — Unlock token correctness, exclusive connection lock (`0x2114` → `[0x01]`), pairing key store/clear commands.

**Phase 4 — Operational sequences** *(ordered, stateful)*

18. **`test_s15_sequences.py`** — One test per §15 sequence, marked `@pytest.mark.sequence`:
    - `test_full_connect_to_bolus` (§15.1)
    - `test_pairing_sequence` (§15.2)
    - `test_priming_sequence` (§15.3)
    - `test_temp_basal_sequence` (§15.4)
    - `test_pause_unpause_sequence` (§15.5)
    - `test_cartridge_replacement_sequence` (§15.6)
    - `test_cancel_temp_basal` (§15.7) — sends `pct=100, duration=0`
    - `test_cancel_active_bolus` (§15.8) — sends `amount=0`
    - `test_shutdown_sequence` (§15.9)

19. **`test_s03_operational_limits.py`** — Boundary value tests: min/max bolus, min/max temp basal %, min/max duration, max basal rate; verify pump rejects out-of-range values with `ERROR_PUMP_BOLUS_REJECTED` (bit 82) / `ERROR_PUMP_TEMPORARY_BASAL_REJECTED` (bit 83).

20. **`test_s17_alert_thresholds.py`** — If simulator supports injecting state: set battery to 25%/10%/5% and check `ERROR_PUMP_ALERT_BATTERY_LEVEL_ALERT` (bit 13) fires; reservoir at 50/25/5 U; cartridge age > 72h.

21. **`test_s18_error_handling.py`** — Reconnect after disconnect restores full state; BLE write succeeds after simulated 700 ms latency.

---

### Relevant files

- [KALEIDO_PUMP_TECHNICAL_MANUAL.md](KALEIDO_PUMP_TECHNICAL_MANUAL.md) — sole source of truth
- `tests/helpers/constants.py` — new, all §4/§11 constants
- `tests/helpers/codec.py` — new, §6/§8/§13/§16 encode/decode functions
- `tests/helpers/ble.py` — new, `notify_and_collect()` pattern
- `tests/conftest.py` — new, `bleak` session fixtures

---

### Verification

1. `pytest tests/ -k "not sequence" --device-address XX:XX:XX:XX:XX:XX` — all protocol unit tests pass
2. `pytest tests/ -m sequence --device-address ... -v` — all 9 sequences pass in order
3. `pytest tests/test_s03_*` — boundary rejections confirmed by alarm bitfield notifications
4. `pytest tests/ --collect-only` — every manual section has ≥ 1 test file

---

### Decisions

- **`bleak`** is the BLE library (Linux-native, ESP32 compatible via HCI)
- **Session-scoped `ble_client`** to avoid repeated BLE connect/disconnect overhead; function-scoped `reset_state` for isolation
- `pytest-asyncio` with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` boilerplate on every test
- `helpers/codec.py` pure functions are also exercised in Phase 2 without hardware (fast CI path)
- Test files prefixed `test_sNN_` to match manual section numbers for traceability

---

### Open Questions

1. **Simulator test injection API** — §17 threshold tests and negative parser tests (wrong-length notifications) require the simulator to expose a way to inject state (battery %, alarm injection). Does the ZephyrOS firmware plan to include a test/debug BLE command for this, or should those tests be marked `xfail`/`skip` until that exists?

2. **Cartridge insertion date format** — §8.16 / §9 mention `LocalDateTime` serialization for `0x210B` but the wire format is described as "variable" with no exact byte layout. Should those tests initially be skipped or use whatever the firmware emits to define the format?

3. **Test ordering** — Sequences in §15 are stateful and destructive (shutdown, cartridge replacement). Should each sequence start with a fresh BLE reconnect (safe, slower) or rely on `reset_state` fixture (faster, fragile)? Recommend reconnect per sequence test for reliability.
