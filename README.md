# Kaleidoscope — Kaleido BLE Protocol Test Suite

`pytest` suite that verifies the Kaleido insulin pump BLE protocol against a ZephyrOS simulator (or real device) section by section. Tests map 1:1 to chapters in `KALEIDO_PUMP_TECHNICAL_MANUAL.md`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running tests

**Phase 2 — pure unit tests (no hardware needed):**
```bash
pytest tests/ -k "not sequence"
```

**Phase 3/4 — BLE tests (requires device):**
```bash
pytest tests/ --device-address XX:XX:XX:XX:XX:XX
```

**Operational sequences only:**
```bash
pytest tests/ -m sequence --device-address XX:XX:XX:XX:XX:XX -v
```

## Test structure

| File | Manual section |
|---|---|
| `test_s06_wire_conventions.py` | §6 Wire format |
| `test_s11_enumerations.py` | §11 Enumerations |
| `test_s12_data_models.py` | §12 Data models |
| `test_s16_unit_conversions.py` | §16 Unit conversions |
| `test_s04_characteristics.py` | §4 BLE characteristics *(needs device)* |
| `test_s05_connection_state.py` | §5 Connection state machine *(needs device)* |
| `test_s07_command_protocol.py` | §7 Command protocol *(needs device)* |
| `test_s08_write_operations.py` | §8 Write operations *(needs device)* |
| `test_s09_read_operations.py` | §9 Read operations *(needs device)* |
| `test_s10_notifications.py` | §10 Notifications *(needs device)* |
| `test_s13_alarm_system.py` | §13 Alarm system *(needs device)* |
| `test_s14_security.py` | §14 Security *(needs device)* |
| `test_s15_sequences.py` | §15 Operational sequences *(needs device)* |
| `test_s17_alert_thresholds.py` | §17 Alert thresholds *(needs device)* |
| `test_s18_error_handling.py` | §18 Error handling *(needs device)* |
