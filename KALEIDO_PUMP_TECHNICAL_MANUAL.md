# Kaleido Insulin Pump — BLE Protocol Technical Manual

> **BLE library:** Nordic Semiconductor Android BLE (`no.nordicsemi.android.kotlin.ble`)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Hardware Specifications](#2-hardware-specifications)
3. [Operational Limits](#3-operational-limits)
4. [BLE Service & Characteristics](#4-ble-service--characteristics)
5. [Connection State Machine](#5-connection-state-machine)
6. [Wire Format Conventions](#6-wire-format-conventions)
7. [Command Protocol (Characteristic 0x2118)](#7-command-protocol-characteristic-0x2118)
8. [Write Operations — Full Reference](#8-write-operations--full-reference)
9. [Read Operations — Full Reference](#9-read-operations--full-reference)
10. [Notification Messages — Full Reference](#10-notification-messages--full-reference)
11. [Enumerations & Constants](#11-enumerations--constants)
12. [Data Model Classes](#12-data-model-classes)
13. [Alarm System](#13-alarm-system)
14. [Security & Crypto Layer](#14-security--crypto-layer)
15. [Operational Sequences](#15-operational-sequences)
16. [Insulin Unit Conversions](#16-insulin-unit-conversions)
17. [Alert & Alarm Thresholds](#17-alert--alarm-thresholds)
18. [Error Handling & Recovery](#18-error-handling--recovery)
19. [Implementation Notes](#19-implementation-notes)

---

## 1. Overview

The Kaleido insulin pump communicates over Bluetooth Low Energy (BLE) using a custom GATT service with proprietary characteristics. A BLE central (controller app) controls the pump entirely through characteristic reads, writes, and notifications.

### Architecture

```
┌─────────────────────┐       BLE        ┌──────────────┐
│  Controller App     │◄────────────────►│  Kaleido Pump │
│                     │                   │  (IDU/Patch)  │
│  KldPumpDataSource  │  GATT R/W/Notify  │              │
│                     │                   │              │
└─────────────────────┘                   └──────────────┘
```

The BLE driver class (`KldPumpDataSource`) manages:
- BLE connection lifecycle (connect, discover services, register notifications)
- All characteristic reads and writes
- Incoming notification message parsing via `KldMessage`
- Connection state machine via `ConnectionState`

---

## 2. Hardware Specifications

From the official Kaleido Guidebook (3711843.pdf) and BLE protocol analysis:

### Physical Characteristics

| Property | Value |
|---|---|
| Pump dimensions | 12.5 mm × 50 mm × 35 mm |
| Pump weight | 19 g |
| Pump battery | 260 mAh rechargeable lithium polymer |
| Pump battery life | > 3 days on full charge |
| Pump service life | 4 years |
| Ingress protection (pump) | IP68 (dustproof, waterproof 1m / 1 hour) |
| Insulin type | U100 rapid-acting only |
| Insulin cartridge max life | 3 days (72 hours) |
| Cartridge capacity | ~200 U (standard Kaleido cartridge) |
| Infusion set cannula sizes | 6 mm and 9 mm |

### BLE Radio

| Property | Value |
|---|---|
| Protocol | Bluetooth® Low Energy |
| Transmitter class | Class 3 (peak 1 mW / 0 dBm) |
| Typical output power | ~0.35 mW |
| Frequency | 2.402 – 2.480 GHz (ISM band) |
| BLE write type | `BleWriteType.DEFAULT` (Write Request with response) |
| CCCD UUID | `00002902-0000-1000-8000-00805f9b34fb` |

### Delivery Accuracy

| Property | Value |
|---|---|
| Delivery accuracy | ±5% in all operating conditions |
| Tested accuracy | -1.0% overall error at 1 U/hr (per IEC 60601-2-24) |
| Maximum infusion pressure at occlusion | 1 bar |
| Maximum time to occlusion alarm | 1 hour at 1 U/hr; 20 hours at 0.05 U/hr |
| Bolus volume generated at occlusion | < 0.5 U |
| Maximum delivery under single fault | 0.05 U |

### Environmental

| Property | Value |
|---|---|
| Operating temperature | 5 – 37 °C (41 – 98.6 °F) |
| Operating humidity | 15 – 93% RH non-condensing |
| Operating pressure | 0.7 – 1.06 bar |

---

## 3. Operational Limits

These values are from the Kaleido Guidebook and confirmed in the wire format analysis. They are **critical** for any implementation — the pump firmware enforces these limits and will reject out-of-range commands via `ERROR_PUMP_BOLUS_REJECTED` (bit 82) and `ERROR_PUMP_TEMPORARY_BASAL_REJECTED` (bit 83).

### Basal Rate

| Parameter | Value | Wire Encoding |
|---|---|---|
| Minimum rate | 0.05 U/hr | byte value `1` |
| Maximum rate | 5.00 U/hr | byte value `100` |
| Increment | 0.05 U/hr | byte value `1` |
| Segments per profile | 24 (one per hour, 0-23) | 24 bytes in profile |
| Profile name | Fixed: `"SECURITY_BASAL_PROFI"` | 20 bytes UTF-8 |

### Bolus (Quick Bolus)

| Parameter | Value | Wire Encoding |
|---|---|---|
| Minimum bolus | 0.05 U (1 pulse) | `0x01 0x00` |
| Maximum bolus | 20.00 U (400 pulses) | `0x90 0x01` |
| Increment | 0.05 U (1 pulse) | |

### Extended Bolus

| Parameter | Value |
|---|---|
| Maximum total bolus | 20.00 U |
| Minimum immediate portion | 0.05 U |
| Maximum immediate portion | 19.95 U |
| Extension duration range | 0.5 – 9.5 hours (30 – 570 minutes) |

### Temporary Basal Rate

| Parameter | Value | Wire Encoding |
|---|---|---|
| Minimum percentage | 0% | `0x00 0x00` |
| Maximum percentage | 200% | `0xC8 0x00` |
| Minimum duration | 0.5 hours (30 minutes) | `0x1E 0x00` |
| Maximum duration | 24 hours (1440 minutes) | `0xA0 0x05` |
| Duration unit (wire) | **minutes** (u16 LE) | |

> **Important:** The temp basal `duration` field in `KldTemporaryBasalRequest` is encoded as **minutes** on the wire (u16 LE). The guidebook presents duration in 0.5-hour increments to the user, but the protocol accepts minute resolution.

### Priming

| Parameter | Value |
|---|---|
| Cannula sizes | 6 mm and 9 mm |
| Prime pump characteristic | `0x2113` — single byte: number of pulses |
| Auto-prime | Pump primes cannula automatically based on selected size |

---

## 4. BLE Service & Characteristics

### UUID Format

All custom Kaleido characteristics share a common base UUID pattern:

```
812321XX-5ea1-589e-004d-6548f98fc73c
```

Where `XX` is the characteristic identifier (hex). The standard Battery Level characteristic uses the Bluetooth SIG UUID.

### Service UUID

The service UUID is derived at runtime during service discovery. The `ClientBleGattService` object stores it as a `java.util.UUID`. The service is discovered by iterating GATT services after connection, and its characteristics are mapped into a `characteristicMap: Map<String, ClientBleGattCharacteristic>` keyed by UUID string.

Based on the UUID pattern and standard BLE practices, the service UUID is likely:
```
81232100-5ea1-589e-004d-6548f98fc73c
```
(The base UUID with `0x2100` as the service identifier.)

### Complete Characteristic Map

#### Notification Characteristics (Read/Notify)

| UUID Short | Full UUID | Real Name | Data Type | Size |
|---|---|---|---|---|
| `0x2100` | `81232100-5ea1-589e-004d-6548f98fc73c` | IDU Mode | `KldIduMode` | 1 byte |
| `0x2101` | `81232101-5ea1-589e-004d-6548f98fc73c` | Alarm Status | `KldAlarmStatus` | variable |
| `0x2104` | `81232104-5ea1-589e-004d-6548f98fc73c` | Reservoir Level | `ReservoirLevel` | 2 bytes |
| `0x2105` | `81232105-5ea1-589e-004d-6548f98fc73c` | Delivery State | `KldDeliveryState` | 1 byte |
| `0x2109` | `81232109-5ea1-589e-004d-6548f98fc73c` | Temp Basal Time Left | `Duration` | variable |
| `0x210B` | `8123210b-5ea1-589e-004d-6548f98fc73c` | Cartridge Insertion Date | `LocalDateTime` | variable |
| `0x210C` | `8123210c-5ea1-589e-004d-6548f98fc73c` | Delivery Type | `KldDeliveryType` | 1 byte |
| `0x210E` | `8123210e-5ea1-589e-004d-6548f98fc73c` | Pump Event | `KldPumpEvent` | variable |
| `0x2112` | `81232112-5ea1-589e-004d-6548f98fc73c` | Current Basal Rate | `int` (pulses) | 2 bytes |
| `0x2A19` | `00002a19-0000-1000-8000-00805f9b34fb` | Battery Level | `int` (percent) | 1 byte |

#### Write-Only Characteristics

| UUID Short | Full UUID | Real Name | Operations |
|---|---|---|---|
| `0x2103` | `81232103-5ea1-589e-004d-6548f98fc73c` | Alarm Acknowledge | `acknowledgeAlarm` |
| `0x2107` | `81232107-5ea1-589e-004d-6548f98fc73c` | Basal Profile | `writeBasalProfile` |
| `0x2108` | `81232108-5ea1-589e-004d-6548f98fc73c` | Temp Basal Request | `sendTempBasalRequest` |
| `0x210A` | `8123210a-5ea1-589e-004d-6548f98fc73c` | Bolus Request | `sendBolusRequest` |
| `0x2111` | `81232111-5ea1-589e-004d-6548f98fc73c` | Insulin On Board | `writeEmptyInsulinOnBoard` |
| `0x2113` | `81232113-5ea1-589e-004d-6548f98fc73c` | Prime Pump | `primePump` |
| `0x2114` | `81232114-5ea1-589e-004d-6548f98fc73c` | Exclusive Connection | `setExclusiveConnection` |
| `0x2115` | `81232115-5ea1-589e-004d-6548f98fc73c` | Total Daily Dose | `writeEmptyTotalDailyDose` |
| `0x2117` | `81232117-5ea1-589e-004d-6548f98fc73c` | System Time | `writeSystemTime` |

#### Dual-Use Characteristics (Read + Write + Notify)

| UUID Short | Full UUID | Read | Write | Notify |
|---|---|---|---|---|
| `0x2100` | `81232100-...` | `readIduMode` | `shutdownPump` | IDU Mode changes |
| `0x2104` | `81232104-...` | `readReservoirLevel` | `writeReservoirLevel` | Reservoir level changes |
| `0x2105` | `81232105-...` | `readDeliveryState` | `updateDelivery` | Delivery state changes |

#### Command Channel

| UUID Short | Full UUID | Description |
|---|---|---|
| `0x2118` | `81232118-5ea1-589e-004d-6548f98fc73c` | Command channel (ring, pairing, unlock) |

---

## 5. Connection State Machine

The connection state is managed by the `ConnectionState` enum:

```
                    ┌──────────────┐
                    │ DISCONNECTED │ (0)
                    └──────┬───────┘
                           │ connect(macAddress)
                    ┌──────▼───────┐
                    │  CONNECTING  │ (1)
                    └──────┬───────┘
                           │ BLE connected
     ┌─────────────────────▼─────────────────────┐
     │ CONNECTED_REGISTERING_STATE_CHANGES (2)   │
     └─────────────────────┬─────────────────────┘
                           │ state change listener registered
     ┌─────────────────────▼─────────────────────┐
     │ CONNECTED_DISCOVERING_SERVICES (3)         │
     └─────────────────────┬─────────────────────┘
                           │ GATT services discovered
     ┌─────────────────────▼─────────────────────┐
     │ CONNECTED_REGISTERING_PUSH (4)             │
     └─────────────────────┬─────────────────────┘
                           │ notifications registered
     ┌─────────────────────▼─────────────────────┐
     │ CONNECTED_AVAILABLE (5)                    │
     └──────┬──────────────────────────────┬─────┘
            │ unlockPump required          │ ready
     ┌──────▼───────┐              ┌───────▼───────┐
     │PENDING_UNLOCK│ (7)          │   (operate)   │
     └──────┬───────┘              └───────────────┘
            │ unlock success
            └──► CONNECTED_AVAILABLE
                           │
                    ┌──────▼───────┐
                    │DISCONNECTING │ (6)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ DISCONNECTED │
                    └──────────────┘
```

### Connection Flow

1. Check BLE permissions and settings
2. Atomically transition `DISCONNECTED → CONNECTING`
3. Launch connection coroutine:
   - Create `ClientBleGatt` via Nordic BLE library
   - Transition `CONNECTING → CONNECTED_REGISTERING_STATE_CHANGES`
   - Register connection state change listener
   - Transition → `CONNECTED_DISCOVERING_SERVICES`
   - Call `discoverServices()` → populates `characteristicMap`
   - Transition → `CONNECTED_REGISTERING_PUSH`
   - Call `registerCharacteristicNotifications()` → subscribes to all notify characteristics
   - Transition → `CONNECTED_AVAILABLE`

### Disconnect Flow

1. Atomically set state to `DISCONNECTED`
2. Cancel coroutine scope
3. Close `ClientBleGatt` connection

---

## 6. Wire Format Conventions

- **Byte order:** All multi-byte values are **Little Endian** (`ByteOrder.LITTLE_ENDIAN`)
- **Integer encoding:** `putShort()` = 16-bit signed, used for most values
- **Single-byte enums:** Enum values encoded as 1 byte directly
- **Command packets:** Prefixed with a 1-byte command ID (see §7)
- **Strings:** UTF-8 encoded via `String.getBytes(StandardCharsets.UTF_8)`
- **Bitmasks:** Alarm bitfields use LSB-first bit ordering in byte arrays

---

## 7. Command Protocol (Characteristic 0x2118)

The command channel `81232118-5ea1-589e-004d-6548f98fc73c` uses a packet format defined by `KldCommand`.

### Packet Structure

```
┌──────────┬───────────────────────┐
│ Byte 0   │ Bytes 1..N            │
│ Cmd ID   │ Payload               │
└──────────┴───────────────────────┘
```

**Serialization:**
```java
byte[] result = new byte[payload.length + 1];
result[0] = (byte) commandId;
System.arraycopy(payload, 0, result, 1, payload.length);
return result;
```

### Command Types

| Command ID | Name | Payload | Total Size | Description |
|---|---|---|---|---|
| `0x01` | StorePairingKey | 16 zero bytes | 17 bytes | Store BLE pairing key on pump |
| `0x02` | ClearPairingKey | 16 zero bytes | 17 bytes | Clear stored pairing key |
| `0x03` | Ring | 16-byte beep pattern | 17 bytes | Make the pump beep/ring |
| `0x05` | UnlockPump | `"OTOphaYROmOgYMER"` (16 bytes UTF-8) | 17 bytes | Unlock pump for operation |

### Special: Ring Pump

The Ring command sends a fixed 16-byte beep pattern followed by the command ID:

**Payload (16 bytes):**
```
0F 07 0F 07 0F 07 0F 00 00 00 00 00 00 00 00 00
```

**Pattern structure:** Three repetitions of `{0x0F, 0x07}` (likely frequency/duration pairs defining the beep pattern), followed by `0x0F` and 9 zero bytes (padding/silence).

**Full wire format (17 bytes):**
```
03 0F 07 0F 07 0F 07 0F 00 00 00 00 00 00 00 00 00
│  └──────────────── Ring payload (16 bytes) ──────┘
└── Command ID = 0x03
```

### Special: Unlock Pump

The unlock command uses a **different write method** (`e()` = `writeCharacteristicUnlockPump`) that bypasses connection state checking, unlike the normal `c()` = `writeCharacteristic` method. This allows unlocking from `PENDING_UNLOCK` state.

**Hardcoded unlock token:**
```
"OTOphaYROmOgYMER"
```

Wire format:
```
05 4F 54 4F 70 68 61 59 52 4F 6D 4F 67 59 4D 45 52
│  └─────────────── "OTOphaYROmOgYMER" UTF-8 ──────┘
└── Command ID = 0x05
```

---

## 8. Write Operations — Full Reference

### 8.1 Send Bolus Request

**Characteristic:** `8123210a-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__SEND_BOLUS_REQUEST`  
**Model class:** `KldPumpBolusRequest`

**Wire format (6 bytes):**
```
┌──────────────┬──────────────┬──────────────┐
│ Bytes 0-1    │ Bytes 2-3    │ Bytes 4-5    │
│ amount (u16) │ 0x0000       │ 0x0000       │
│ LE           │ reserved     │ reserved     │
└──────────────┴──────────────┴──────────────┘
```

**Serialization:**
```java
ByteBuffer.allocate(6)
    .order(ByteOrder.LITTLE_ENDIAN)
    .putShort((short) amount)   // bolus amount in PULSES
    .putShort((short) 0)        // reserved
    .putShort((short) 0)        // reserved
    .array();
```

> **Unit:** Amount is in **pulses**, not insulin units. 1 pulse = 0.05 U. See §17.

### 8.2 Send Temporary Basal Request

**Characteristic:** `81232108-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__SEND_TEMP_BASAL_REQUEST`  
**Model class:** `KldTemporaryBasalRequest`

**Wire format (4 bytes):**
```
┌────────────────┬────────────────┐
│ Bytes 0-1      │ Bytes 2-3      │
│ percentage     │ duration       │
│ (u16 LE)       │ (u16 LE)       │
└────────────────┴────────────────┘
```

**Serialization:**
```java
ByteBuffer.allocate(4)
    .order(ByteOrder.LITTLE_ENDIAN)
    .putShort((short) percentage)  // e.g., 100 = 100%
    .putShort((short) duration)    // in minutes
    .array();
```

**Constant:** `LENGTH = 4`

### 8.3 Write System Time

**Characteristic:** `81232117-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__WRITE_SYSTEM_TIME`  
**Model class:** `KldSystemTime`

**Wire format (9 bytes):**
```
┌──────────┬───────┬─────┬───────┬─────────┬─────────┬─────────────────┬───────────────┐
│ Bytes 0-1│ Byte 2│Byte3│ Byte 4│ Byte 5  │ Byte 6  │ Byte 7          │ Byte 8        │
│ year     │ month │ day │ hours │ minutes │ seconds │ timeChangeIndex │ rollOverCount │
│ (u16 LE) │ (u8)  │(u8) │ (u8)  │ (u8)    │ (u8)    │ (u8)            │ (u8)          │
└──────────┴───────┴─────┴───────┴─────────┴─────────┴─────────────────┴───────────────┘
```

**Serialization:**
```java
ByteBuffer.allocate(9)
    .order(ByteOrder.LITTLE_ENDIAN)
    .putShort((short) year)
    .put((byte) month)
    .put((byte) day)
    .put((byte) hours)
    .put((byte) minutes)
    .put((byte) seconds)
    .put((byte) timeChangeIndex)
    .put((byte) rollOverCount)
    .array();
```

**Parse (reading back):** Accepts byte arrays of length **9** or **113** (the larger size likely includes additional pump event data).

**Constant:** `DATA_SIZE = 9`

### 8.4 Write Basal Profile

**Characteristic:** `81232107-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__SET_BASAL_PROFILE`  
**Model class:** `KldBasalProfile`

**Wire format (44 bytes):**
```
┌────────────────────────────┬──────────────────────────┐
│ Bytes 0-19                 │ Bytes 20-43              │
│ Profile Name (UTF-8)       │ 24 hourly rate bytes     │
│ "SECURITY_BASAL_PROFI"     │ rate[0]..rate[23]        │
│ zero-padded to 20 bytes    │                          │
└────────────────────────────┴──────────────────────────┘
```

**Rate encoding:** Each rate byte represents the basal rate for one hour (hour 0-23):
```
rate_byte = round(abs(rate_in_units_per_hour) / 0.05)
```
Clamped to max 100 (= 5.0 U/hr).

**Constants:**
```
BASAL_PROFILE_NAME = "SECURITY_BASAL_PROFI"
BASAL_PROFILE_NAME_SIZE = 20
BASAL_PROFILE_SIZE = 24
```

**Basal Segments** are defined by `KldBasalSegment` with fields:
- `startOffset` (long) — start time in milliseconds from midnight
- `duration` (long) — duration in milliseconds
- `rate` (double) — rate in U/hr
- `rateType` (enum) — rate classification

The profile builder sorts segments by start time, then for each of the 24 hours, finds the matching segment and encodes its rate.

### 8.5 Update Delivery State

**Characteristic:** `81232105-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__UPDATE_DELIVERY_STATE`

**Wire format (1 byte):**
```
┌────────┐
│ Byte 0 │
│ state  │
└────────┘
```

Values — see `KldDeliveryState` enum in §12.

### 8.6 Prime Pump

**Characteristic:** `81232113-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__PRIME_PUMP`

**Wire format (1 byte):**
```
┌────────┐
│ Byte 0 │
│ nbPulse│
└────────┘
```

The number of priming pulses to execute.

### 8.7 Shutdown Pump

**Characteristic:** `81232100-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__SHUTDOWN_PUMP`

**Wire format (1 byte):**
```
┌────────┐
│ Byte 0 │
│ 0x04   │
└────────┘
```

Always sends `KldIduMode.SHUTDOWN.getValue()` = `4`.

### 8.8 Acknowledge Alarm

**Characteristic:** `81232103-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__ACKNOWLEDGE_ALARMS`

**Wire format (18 bytes):**

A 144-bit (18-byte) bitfield encoded LSB-first. Each alarm has a `bitIndex` (see §13). To acknowledge alarm(s):

```java
BitSet bitSet = new BitSet(160);
for (KldAlarm alarm : alarmsToAcknowledge) {
    bitSet.set(alarm.getBitIndex() + 6, true);
}
// Convert BitSet to 18-byte array (LSB-first)
```

The +6 offset accounts for the first 6 reserved bits in the alarm bitfield.

### 8.9 Write Reservoir Level

**Characteristic:** `81232104-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__WRITE_RESERVOIR_LEVEL`  
**Model class:** `ReservoirLevel`

**Wire format (2 bytes):**
```
┌──────────────────────┐
│ Bytes 0-1            │
│ reservoirLevelInPulse│
│ (u16 LE)             │
└──────────────────────┘
```

The reservoir level is in **pulses** (1 pulse = 0.05 U).

### 8.10 Set Exclusive Connection

**Characteristic:** `81232114-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__SET_EXCLUSIVE_CONNECTION`

**Wire format (1 byte):**
```
┌────────┐
│ Byte 0 │
│ 0x01   │
└────────┘
```

Always sends `{1}`. Used to claim exclusive control over the pump.

### 8.11 Write Empty Insulin On Board

**Characteristic:** `81232111-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__WRITE_EMPTY_INSULIN_ON_BOARD`

**Wire format:**
- **50 bytes** of zeros (standard path)
- **82 bytes** of zeros (alternate path, likely version-dependent)

Resets the pump's IOB tracking.

### 8.12 Write Empty Total Daily Dose

**Characteristic:** `81232115-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__WRITE_EMPTY_TOTAL_DAILY_DOSE`

**Wire format:**
- **14 bytes** of zeros (standard path)
- **110 bytes** of zeros (alternate path, likely version-dependent)

Resets the pump's TDD tracking.

### 8.13 Store Pairing Key

**Characteristic:** `81232118-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__STORE_PAIRING_KEY`

Uses Command Protocol: Command ID `0x01` + 16 zero bytes payload.

### 8.14 Clear Pairing Key

**Characteristic:** `81232118-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__CLEAR_PAIRING_KEY`

Uses Command Protocol: Command ID `0x02` + 16 zero bytes payload.

### 8.15 Ring Pump

**Characteristic:** `81232118-5ea1-589e-004d-6548f98fc73c`  
**Analytics event:** `KLD__DATASOURCE__RING`

Uses Command Protocol: Command ID `0x03` + 16-byte fixed beep pattern.

**Wire format (17 bytes total):**
```
03 0F 07 0F 07 0F 07 0F 00 00 00 00 00 00 00 00 00
│  └──────────────── Beep pattern (16 bytes) ──────┘
└── Command ID = 0x03
```

The payload is a hardcoded 16-byte array: `{0x0F, 0x07, 0x0F, 0x07, 0x0F, 0x07, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}`. The three `{0x0F, 0x07}` pairs likely represent frequency/duration beep parameters.

### 8.16 Write Cartridge Insertion Date

**Characteristic:** `8123210b-5ea1-589e-004d-6548f98fc73c`  
**Method:** `writeCartridgeInsertionDate`  
**Parameter:** `localDateTime: LocalDateTime`

Writes the cartridge insertion timestamp to the pump. Used during the pairing/cartridge-insertion flow to record when the current insulin cartridge was loaded. The wire format is a serialized `LocalDateTime`.

> **Note for implementers:** This characteristic is the same UUID (`0x210B`) used for `readCartridgeInsertionDate`. It is read to track how long the current cartridge has been in use (3-day limit) and written when a new cartridge is inserted.

---

## 9. Read Operations — Full Reference

All read operations use `readCharacteristic(characteristic, shouldCheckConnectionState)` which reads raw bytes from the characteristic and parses them.

| Method | Returns | Characteristic | Parse Logic |
|---|---|---|---|
| `getPumpVersion()` | `String?` | Read, parse as string | Firmware version |
| `readSystemTime()` | `KldSystemTime?` | `0x2117` (likely read variant) | 9-byte LE → year,month,day,h,m,s,tci,roc |
| `readIduMode()` | `KldIduMode?` | `0x2100` | 1 byte → enum value |
| `readDeliveryState()` | `KldDeliveryState?` | `0x2105` | 1 byte → enum value |
| `readDeliveryType()` | `KldDeliveryType?` | `0x210C` | 1 byte → bitmask (see §11) |
| `readTemporaryBasalTimeLeft()` | `Duration?` | `0x2109` | 2 bytes LE → minutes → Duration |
| `readCurrentBasalRate()` | `Double?` | `0x2112` | 2 bytes LE → pulses → U/hr |
| `readReservoirLevel()` | `ReservoirLevel?` | `0x2104` | 2 bytes LE → pulses |
| `readCartridgeInsertionDate()` | `LocalDateTime?` | `0x210B` | Variable → timestamp |
| `readBatteryLevel()` | `Int?` | `0x2A19` | 1 byte → percent |
| `readAlarmStatus()` | `KldAlarmStatus?` | `0x2101` | 20 bytes → bitfield parse |
| `readUnacknowledgedAlarms()` | `List<KldAlarm>?` | (via alarm status) | 20 bytes → alarm list |

---

## 10. Notification Messages — Full Reference

### Message Parser

The central parser is `KldMessage.Companion.parse(UUID uuid, byte[] data)`. It switches on the UUID string of the characteristic that sent the notification:

```
UUID → Parser Class → KldMessage subtype
```

| UUID (short) | Parsed Type | DATA_SIZE |
|---|---|---|
| `81232100` | `IduModeMessage(iduMode: KldIduMode)` | 1 byte |
| `81232101` | `AlarmStatusMessage(alarmStatus: KldAlarmStatus)` | 20 bytes |
| `81232104` | `ReservoirLevelMessage(reservoirLevel: ReservoirLevel)` | 2 bytes |
| `81232105` | `DeliveryStateMessage(deliveryState: KldDeliveryState)` | 1 byte |
| `81232109` | `TemporaryBasalTimeLeftMessage(duration: Duration)` | 2 bytes |
| `8123210b` | `RemainingBolusMessage(remainingBolusPulses: int)` | 2 bytes |
| `8123210c` | `DeliveryTypeMessage(deliveryType: KldDeliveryType)` | 1 byte |
| `8123210e` | `PumpEventMessage` (abstract, see subtypes below) | ≥ 12 bytes |
| `81232112` | `CurrentBasalRateMessage(currentBasalRateInPulses: int)` | 2 bytes |
| `00002a19` | `BatteryLevelMessage(batteryLevel: int)` | 1 byte |
| *(default)* | `UnknownMessage` (singleton) | — |

### Parse Pattern

All parsers follow the same pattern:
1. Check `data.length == DATA_SIZE` (return `ParsingFailureMessage` if wrong)
2. Extract first byte(s) from data
3. Map to enum/value (return `ParsingFailureMessage` if invalid)
4. Wrap in message object

Example (IduMode, DATA_SIZE=1):
```java
if (data.length != 1) return ParsingFailureMessage.INSTANCE;
Byte b = data[0];
KldIduMode mode = KldIduMode.Companion.fromByte(b);
if (mode == null) return ParsingFailureMessage.INSTANCE;
return new IduModeMessage(mode);
```

---

## 11. Enumerations & Constants

### KldIduMode

The IDU (Insulin Delivery Unit) operational mode:

| Name | Value | Description |
|---|---|---|
| `BOOT` | `0` | Pump is booting |
| `IDLE` | `1` | Pump is idle (not delivering) |
| `ALARM` | `2` | Pump is in alarm state |
| `DELIVERY` | `3` | Pump is actively delivering insulin |
| `SHUTDOWN` | `4` | Pump is shutting down |

### KldDeliveryState

| Name | Value | Description |
|---|---|---|
| `UNDEFINED` | `0` | Unknown/uninitialized |
| `STOPPED` | `1` | Delivery stopped |
| `PAUSED` | `2` | Delivery paused |
| `PRIMING` | `3` | Pump is priming |
| `DELIVERING` | `4` | Actively delivering insulin |

### KldDeliveryType

A bitmask decoded from a single byte:

| Bit | Mask | Field | Meaning |
|---|---|---|---|
| 0 | `0x01` | `isBasal` | Basal delivery active |
| 1 | `0x02` | `isTemporaryBasal` | Temporary basal active |
| 2 | `0x04` | `isBolus` | Bolus delivery active |

Example: value `0x05` = basal + bolus active.

### ConnectionState

| Name | Value | Description |
|---|---|---|
| `DISCONNECTED` | `0` | Not connected |
| `CONNECTING` | `1` | BLE connection in progress |
| `CONNECTED_REGISTERING_STATE_CHANGES` | `2` | Registering for BLE state callbacks |
| `CONNECTED_DISCOVERING_SERVICES` | `3` | GATT service discovery |
| `CONNECTED_REGISTERING_PUSH` | `4` | Subscribing to notifications |
| `CONNECTED_AVAILABLE` | `5` | Ready for operation |
| `DISCONNECTING` | `6` | Disconnection in progress |
| `PENDING_UNLOCK` | `7` | Waiting for unlock command |

### Analytics Events

| Event Name | Operation |
|---|---|
| `KLD__DATASOURCE__RING` | Ring pump |
| `KLD__DATASOURCE__ACKNOWLEDGE_ALARMS` | Acknowledge alarm(s) |
| `KLD__DATASOURCE__WRITE_SYSTEM_TIME` | Write system time |
| `KLD__DATASOURCE__SET_BASAL_PROFILE` | Write basal profile |
| `KLD__DATASOURCE__PRIME_PUMP` | Prime pump |
| `KLD__DATASOURCE__UPDATE_DELIVERY_STATE` | Update delivery state |
| `KLD__DATASOURCE__WRITE_EMPTY_INSULIN_ON_BOARD` | Reset IOB |
| `KLD__DATASOURCE__WRITE_EMPTY_TOTAL_DAILY_DOSE` | Reset TDD |
| `KLD__DATASOURCE__SEND_BOLUS_REQUEST` | Send bolus |
| `KLD__DATASOURCE__SEND_TEMP_BASAL_REQUEST` | Send temp basal |
| `KLD__DATASOURCE__SET_EXCLUSIVE_CONNECTION` | Claim exclusive |
| `KLD__DATASOURCE__WRITE_RESERVOIR_LEVEL` | Write reservoir level |
| `KLD__DATASOURCE__STORE_PAIRING_KEY` | Store pairing key |
| `KLD__DATASOURCE__CLEAR_PAIRING_KEY` | Clear pairing key |
| `KLD__DATASOURCE__SHUTDOWN_PUMP` | Shutdown pump |
| `KLD__DATASOURCE__CONNECT_ASKED` | Connect initiated |
| `KLD__DATASOURCE__DISCONNECT_ASKED` | Disconnect initiated |
| `KLD__DATASOURCE__DISCONNECT_DONE` | Disconnect completed |
| `KLD__DATASOURCE__COLLECT_NOTIFICATIONS__FINISHED` | Notification stream ended |

---

## 12. Data Model Classes

### KldSystemTime

**Fields:**

| Field | Type | Wire Offset | Wire Size |
|---|---|---|---|
| `year` | `int` | 0 | 2 bytes (u16 LE) |
| `month` | `int` | 2 | 1 byte |
| `day` | `int` | 3 | 1 byte |
| `hours` | `int` | 4 | 1 byte |
| `minutes` | `int` | 5 | 1 byte |
| `seconds` | `int` | 6 | 1 byte |
| `timeChangeIndex` | `int` | 7 | 1 byte |
| `rollOverCount` | `int` | 8 | 1 byte |

**Factory method:** `Companion.a(LocalDateTime, timeChangeIndex, rollOverCount)` — creates from system clock.

### ReservoirLevel

**Fields:**

| Field | Type | Wire Size |
|---|---|---|
| `reservoirLevelInPulse` | `int` | 2 bytes (u16 LE) |

**Conversion:**
- To units: `reservoirLevelInPulse * 0.05` (via `PulseConverter.mH()`)
- From units: `round(units / 0.05)` (via `PulseConverter.T()`)

### KldBasalProfile

**Structure:** 44-byte packet = 20-byte name + 24-byte rate array

The profile contains an optional list of `KldBasalSegment` objects.

**KldBasalSegment fields:**
| Field | Type | Description |
|---|---|---|
| `startOffset` | `long` | Start time (ms from midnight) |
| `duration` | `long` | Duration (ms) |
| `rate` | `double` | Rate in U/hr |
| `rateType` | enum | Rate classification |

### KldPumpBolusRequest

**Fields:**

| Field | Type | Wire Size |
|---|---|---|
| `amount` | `int` | 2 bytes (u16 LE) |
| *(reserved)* | — | — | 2 bytes (zeros) |
| *(reserved)* | — | — | 2 bytes (zeros) |

**Total wire size:** 6 bytes.

### KldTemporaryBasalRequest

**Fields:**

| Field | Type | Wire Size |
|---|---|---|
| `percentage` | `int` | 2 bytes (u16 LE) |
| `duration` | `int` | 2 bytes (u16 LE) |

**Total wire size:** 4 bytes (`LENGTH = 4`).

### KldAlarmStatus

**Fields:**

| Field | Type | Description |
|---|---|---|
| `isHighAlarm` | `boolean` | Critical alarm active |
| `isMediumAlarm` | `boolean` | Warning alarm active |
| `isAlert` | `boolean` | Informational alert active |
| `activeAlarmList` | `List<KldAlarm>` | List of active alarms |

---

## 13. Alarm System

### KldAlarm Enum

All 74 alarm types with their bit indices (used in the 160-bit alarm bitfield):

#### Critical Errors (Hardware)

| Alarm | Bit Index |
|---|---|
| `ERROR_POF_VCC_NRF_LOW` | 0 |
| `ERROR_ADC_10V_HIGH` | 2 |
| `ERROR_ADC_10V_LOW` | 3 |
| `ERROR_PUMP_CONSTANT_CURRENT_FAILURE` | 4 |
| `ERROR_PUMP_BOOTLOADER_NOT_CONFIGURED` | 5 |
| `ERROR_PUMP_ACTUATOR_NOT_POWERFUL_ENOUGH` | 6 |
| `ERROR_PUMP_ALARM_1006_NOT_COMPLETED_BEFORE_PULSE` | 7 |

#### Battery & Consumable Alerts

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_ALARM_BATTERY_FLAT` | 10 |
| `ERROR_PUMP_ALARM_RESERVOIR_EMPTY` | 11 |
| `ERROR_PUMP_ALARM_CARTRIDGE_EXPIRED` | 12 |
| `ERROR_PUMP_ALERT_BATTERY_LEVEL_ALERT` | 13 |
| `ERROR_PUMP_ALERT_RESERVOIR_LEVEL_ALERT` | 14 |
| `ERROR_PUMP_ALERT_CARTRIDGE_EXPIRING_SOON` | 15 |

#### Occlusion & Delivery

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_OCCLUSION` | 16 |
| `ERROR_PUMP_PULSE_PRECONDITION_FAIL` | 30 |
| `ERROR_PUMP_IMPOSSIBLE_EXTENDED_BOLUS` | 31 |
| `ERROR_PUMP_UNEXPECTED_PULSE` | 84 |

#### Memory Errors

| Alarm | Bit Index |
|---|---|
| `ERROR_FRAM_WRITE_FAIL` | 20 |
| `ERROR_FRAM_READ_FAIL` | 21 |
| `ERROR_FRAM_INVALID_OPERATION` | 22 |
| `ERROR_PUMP_PSM_GETRESULT_BLOCKED` | 23 |
| `ERROR_PUMP_PSM_CRC_FAIL` | 85 |

#### POST (Power On Self Test) Failures

| Alarm | Bit Index |
|---|---|
| `ERROR_POST_PROCESSOR_REG_FAIL` | 40 |
| `ERROR_POST_PROCESSOR_FLAGS_FAIL` | 41 |
| `ERROR_POST_PROCESSOR_INSTRUCTION_FAIL` | 42 |
| `ERROR_POST_CLOCK_FREQ_FAIL` | 45 |
| `ERROR_POST_RAM_ADDRESS_FAIL` | 46 |
| `ERROR_POST_RAM_AA_FAIL` | 47 |
| `ERROR_POST_RAM_55_FAIL` | 48 |
| `ERROR_POST_RAM_RESULT_FAIL` | 49 |

#### Occlusion Sensor

| Alarm | Bit Index |
|---|---|
| `ERROR_OCCLUSION_SENSOR_FAILED_TO_INITIALISE` | 52 |
| `ERROR_OCCLUSION_I2C_FAILURE` | 55 |
| `ERROR_OCCLUSION_VALUE_FAILED_TO_STABILIZE` | 56 |

#### System Errors

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_BLE_INITIALISATION` | 61 |
| `ERROR_PUMP_UNEXPECTED_RESET` | 70 |
| `ERROR_PUMP_HARDWARE_WATCHDOG_PIN_RESET` | 71 |
| `ERROR_PUMP_HARDFAULT` | 72 |
| `ERROR_PUMP_NMI` | 73 |
| `ERROR_PUMP_CPULOCKUP` | 74 |
| `ERROR_PUMP_UNEXPECTED_SW_RESET` | 75 |
| `ERROR_PUMP_ASSERT` | 76 |

#### NRF (BLE Processor) Rejections

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_NRF_IDU_MODE_REJECTED` | 77 |
| `ERROR_PUMP_NRF_DELIVERY_STATE_REJECTED` | 78 |
| `ERROR_PUMP_NRF_BASAL_PROFILE_REJECTED` | 79 |
| `ERROR_PUMP_NRF_ALARM_ACK_REJECTED` | 80 |
| `ERROR_PUMP_NRF_PRIMING_DATA_REJECTED` | 81 |
| `ERROR_PUMP_BOLUS_REJECTED` | 82 |
| `ERROR_PUMP_TEMPORARY_BASAL_REJECTED` | 83 |

#### Other Errors

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_CARTRIDGE_OUT` | 90 |
| `ERROR_PUMP_UNEXPECTED_SHUTDOWN` | 91 |
| `ERROR_PUMP_WITH_NORDIC_PROCESSOR` | 92 |
| `ERROR_PUMP_WHEN_WRITING_PUMP_EVENT` | 93 |
| `ERROR_PUMP_INVALID_PERSISTENT_MEMORY_VERSION` | 94 |
| `ERROR_PUMP_ERASED_PERSISTENT_MEMORY` | 95 |

#### RTC & Driver Failures

| Alarm | Bit Index |
|---|---|
| `ERROR_PUMP_RTC_COUNTER_FAIL` | 100 |
| `ERROR_PUMP_RTC_OFFSET_FAIL` | 101 |
| `ERROR_PUMP_RTC_FREQ_FAIL_LO` | 102 |
| `ERROR_PUMP_RTC_FREQ_FAIL` | 103 |
| `ERROR_PUMP_TIMER_DRIVER_FAIL` | 111 |
| `ERROR_PUMP_PERIPHERAL_INTERFACE_FAIL` | 112 |
| `ERROR_PUMP_ONE_SHOT_TIMER_FAIL` | 113 |
| `ERROR_PUMP_RTC_FAIL` | 114 |
| `ERROR_PUMP_SUPPLY_HOLD_FAIL` | 115 |
| `ERROR_PUMP_UART_INIT_FAIL` | 116 |
| `ERROR_PUMP_BLE_PERIPH_DRIVER_FAIL` | 117 |
| `ERROR_PUMP_I2C_DRIVER_INIT_FAIL` | 118 |
| `ERROR_PUMP_AUDIO_DRIVER_INIT_FAIL` | 119 |
| `ERROR_PUMP_PUMP_ACTUATOR_DRIVER_FAIL` | 120 |
| `ERROR_PUMP_GAS_GAUGE_DRIVER_FAIL` | 121 |
| `ERROR_PUMP_FRAM_DRIVER_FAIL` | 122 |
| `ERROR_PUMP_FAULT_LED_DRIVER_FAIL` | 123 |
| `ERROR_PUMP_POWER_ON_DRIVER_FAIL` | 124 |
| `ERROR_PROXIMITY_SENSOR_DRIVER_FAIL` | 125 |
| `ERROR_ALARM_DEFINITION_MISMATCH_PUMP` | 137 |

### Alarm Bitfield Format

Alarms are encoded as a 160-bit (20-byte) bitfield:
- Byte order: LSB-first (bit 0 of byte 0 = alarm bit 0)
- Bit index = `KldAlarm.bitIndex + 6` (6-bit offset from start)
- The alarm serializer reads/writes 18-byte arrays for acknowledgment and 20-byte arrays for reading status.

**Reading alarms:**
```java
// Parse 20-byte notification data into alarm list
BitSet bits = bytesToBitSet(data);  // LSB-first
List<KldAlarm> alarms = new ArrayList<>();
for (int i = 6; i < 160; i++) {
    if (!bits.get(i)) {  // NOTE: inverted logic - 0 = alarm active
        KldAlarm alarm = KldAlarm.fromBitIndex(i - 6);
        if (alarm != null) alarms.add(alarm);
    }
}
```

**Acknowledging alarms:**
```java
// Build 18-byte acknowledgment payload
BitSet bitSet = new BitSet(160);
for (KldAlarm alarm : alarmsToAck) {
    bitSet.set(alarm.getBitIndex() + 6, true);
}
byte[] payload = bitSetToBytes(bitSet);  // 18 bytes, LSB-first
```

---

## 14. Security & Crypto Layer

The Kaleido pump BLE protocol uses **NO application-layer encryption, MAC, or signing** on any characteristic data. All bytes written to and read from BLE characteristics pass through in **plaintext** with zero transformation.

### Verification of No App-Layer Crypto

The write path was traced end-to-end:

```
app serializes byte[] (e.g., bolus request)
  → writeCharacteristic(byte[], characteristic)      [static wrapper]
    → writeCharacteristicInternal(byte[], characteristic, boolean)  [core write]
      → write coroutine:
          characteristic.write(new DataByteArray(rawBytes), BleWriteType.DEFAULT, ...)
                               ^^^^^^^^^^^^^^^^^^^^^^^^^
                               raw bytes, no transformation
```

The read/notification path is equally transparent:

```
BLE notification arrives as DataByteArray
  → onCharacteristicPushReceived(characteristic, dataByteArray)
    → KldMessage.parse(uuid, dataByteArray.getValue())
                              ^^^^^^^^^^^^^^^^^^^^^^^^
                              raw bytes, parsed directly
```

There is no application-layer crypto (AES, HMAC, etc.) applied to any pump BLE data.

### Security Model (3 layers)

#### Layer 1: BLE Link-Layer Encryption

Standard BLE pairing/bonding handled by the OS. BLE Secure Connections provide AES-CCM encryption at the link layer. The pump-side pairing is managed via:
- `storePairingKey` (Command ID `0x01`) — signals the pump to persist the BLE bond
- `clearPairingKey` (Command ID `0x02`) — clears a previously stored bond

#### Layer 2: Pump Unlock Token

After BLE connection, the pump enters `PENDING_UNLOCK` state and requires an unlock command before accepting any operational writes. The unlock uses a **hardcoded 16-byte ASCII token**:

```
Token: "OTOphaYROmOgYMER" (ASCII, 16 bytes)
Hex:   4F 54 4F 70 68 61 59 52 4F 6D 4F 67 59 4D 45 52
```

Sent via Command ID `0x05` to characteristic `0x2118`. The unlock write method bypasses `CONNECTED_AVAILABLE` state checks (since the pump is still in `PENDING_UNLOCK`).

> **Security implication:** Any device bonded to the pump can unlock it with this static token. There is no per-device secret, challenge-response, or session key exchange.

#### Layer 3: Exclusive Connection Lock

Writing `{0x01}` to characteristic `0x2114` claims exclusive control. This prevents a second bonded device from issuing commands while the first is active.

---

## 15. Operational Sequences

### 15.1 Full Connect-to-Bolus Sequence

```
1.  connect(macAddress)
    → State: DISCONNECTED → CONNECTING → ... → CONNECTED_AVAILABLE

2.  unlockPump()
    → Write 0x2118: [05, "OTOphaYROmOgYMER"]
    → State: PENDING_UNLOCK → CONNECTED_AVAILABLE

3.  setExclusiveConnection()
    → Write 0x2114: [01]

4.  readIduMode()
    → Read 0x2100: expect DELIVERY (3) or IDLE (1)

5.  readDeliveryState()
    → Read 0x2105: expect DELIVERING (4)

6.  readReservoirLevel()
    → Read 0x2104: check sufficient insulin

7.  sendBolusRequest(amount_in_pulses)
    → Write 0x210A: [amount_LE, 00 00, 00 00]
    → Monitor 0x2105 notifications for delivery confirmation
```

### 15.2 Pairing Sequence

```
1.  connect(macAddress)
    → BLE connection + service discovery

2.  storePairingKey()
    → Write 0x2118: [01, 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00]

3.  unlockPump()
    → Write 0x2118: [05, "OTOphaYROmOgYMER"]

4.  writeSystemTime(now)
    → Write 0x2117: [year_LE, month, day, h, m, s, tci, roc]

5.  writeBasalProfile(profile)
    → Write 0x2107: [name_20bytes, rates_24bytes]

6.  writeEmptyInsulinOnBoard()
    → Write 0x2111: [50 or 82 zero bytes]

7.  writeEmptyTotalDailyDose()
    → Write 0x2115: [14 or 110 zero bytes]
```

### 15.3 Priming Sequence

```
1.  (connected + unlocked)

2.  updateDelivery(PRIMING)
    → Write 0x2105: [03]

3.  primePump(nbPulse)
    → Write 0x2113: [nbPulse]
    → Wait for completion (monitor notifications)

4.  updateDelivery(DELIVERING)
    → Write 0x2105: [04]
```

### 15.4 Temporary Basal Sequence

```
1.  (connected + unlocked + delivering)

2.  sendTempBasalRequest(percentage, duration_minutes)
    → Write 0x2108: [percentage_LE, duration_LE]
    → Monitor 0x210C for DeliveryType change (isTemporaryBasal = true)
```

### 15.5 Pause/Unpause Sequence

```
1.  (connected + unlocked + delivering)

2.  updateDelivery(PAUSED)
    → Write 0x2105: [02]
    → Monitor 0x2105 for DeliveryState → PAUSED
    → Pump stops all insulin delivery
    → App should track missed basal insulin (informational only)

3.  (when ready to resume)
    updateDelivery(DELIVERING)
    → Write 0x2105: [04]
    → Monitor 0x2105 for DeliveryState → DELIVERING
    → Pump resumes basal profile
    → Take BG reading after resuming
```

> **Warning (from guidebook):** The pump does NOT automatically deliver missed insulin when unpaused. Any catch-up dosing must be manually calculated and administered as a bolus.

### 15.6 Cartridge Replacement Sequence

```
1.  updateDelivery(STOPPED)
    → Write 0x2105: [01]

2.  (physically: remove old cartridge, insert new filled cartridge)

3.  Pump detects new cartridge → handset reconnects

4.  storePairingKey()
    → Write 0x2118: [01, 00...00]

5.  unlockPump()
    → Write 0x2118: [05, "OTOphaYROmOgYMER"]

6.  writeCartridgeInsertionDate(now)
    → Write 0x210B: [serialized LocalDateTime]

7.  writeReservoirLevel(fullLevel)
    → Write 0x2104: [level_u16_LE]   (e.g., 4000 pulses = 200 U)

8.  (optional) Prime cannula if new infusion set:
    updateDelivery(PRIMING) → primePump(nbPulse) → wait → updateDelivery(DELIVERING)

9.  writeBasalProfile(profile)
    → Write 0x2107: [44 bytes]

10. updateDelivery(DELIVERING)
    → Write 0x2105: [04]
```

### 15.7 Cancel Temporary Basal

To stop an active temporary basal rate before its scheduled end:
```
1.  sendTempBasalRequest(percentage=100, duration=0)
    → Write 0x2108: [64 00, 00 00]
    → Monitor 0x210C for DeliveryType (isTemporaryBasal → false)
```

### 15.8 Cancel Active Bolus

To stop an in-progress bolus:
```
1.  sendBolusRequest(amount=0)
    → Write 0x210A: [00 00, 00 00, 00 00]
    → Monitor 0x210C for DeliveryType (isBolus → false)
```

### 15.9 Shutdown Sequence

```
1.  (connected + unlocked)

2.  shutdownPump()
    → Write 0x2100: [04]  (SHUTDOWN value)
    → Monitor 0x2100 for IduMode → SHUTDOWN
    → disconnect()
```

---

## 16. Insulin Unit Conversions

The Kaleido pump internally works in **pulses**. The conversion factor is:

```
1 pulse = 0.05 U (insulin units)
```

### Conversion Functions

**Pulses to Units:**
```java
double units = pulses * 0.05;
// Rounded to 3 decimal places:
units = Math.rint(units * 1000.0) / 1000.0;
```

**Units to Pulses:**
```java
int pulses = (int) Math.rint(units / 0.05);
```

### Basal Rate Encoding

For basal profile rates:
```java
byte rateByte = (byte) Math.min(100, (int) Math.rint(Math.abs(rateInUnitsPerHour) / 0.05));
```

This means:
- Rate byte `0` = 0.00 U/hr
- Rate byte `1` = 0.05 U/hr
- Rate byte `20` = 1.00 U/hr
- Rate byte `100` = 5.00 U/hr (maximum)

### Example Calculations

| Desired Dose | In Pulses | Wire Bytes (LE) |
|---|---|---|
| 0.5 U bolus | 10 | `0A 00` |
| 1.0 U bolus | 20 | `14 00` |
| 5.0 U bolus | 100 | `64 00` |
| 10.0 U bolus | 200 | `C8 00` |

---

## 17. Alert & Alarm Thresholds

From the Kaleido Guidebook — these are the conditions that trigger alerts and alarms:

### Alerts (non-critical, pump continues delivering)

| Alert | Trigger Thresholds | Alarm Enum |
|---|---|---|
| Battery low | 25%, then 10%, then 5% remaining | `ERROR_PUMP_ALERT_BATTERY_LEVEL_ALERT` (bit 13) |
| Reservoir low | 50 U, then 25 U, then 5 U remaining | `ERROR_PUMP_ALERT_RESERVOIR_LEVEL_ALERT` (bit 14) |
| Cartridge expiring | 12h before expiry, then 6h, then 2h | `ERROR_PUMP_ALERT_CARTRIDGE_EXPIRING_SOON` (bit 15) |
| Communication error | BLE connection lost/degraded | *(handset-side only)* |

### Alarms (critical, pump stops delivering)

| Alarm | Condition | Alarm Enum |
|---|---|---|
| Battery flat | Pump battery fully depleted | `ERROR_PUMP_ALARM_BATTERY_FLAT` (bit 10) |
| Reservoir empty | No insulin remaining | `ERROR_PUMP_ALARM_RESERVOIR_EMPTY` (bit 11) |
| Cartridge expired | Cartridge in use > 3 days (72 hours) | `ERROR_PUMP_ALARM_CARTRIDGE_EXPIRED` (bit 12) |
| Occlusion | Insulin blockage detected (> 1 bar) | `ERROR_PUMP_OCCLUSION` (bit 16) |
| Cartridge out | Cartridge removed from pump | `ERROR_PUMP_CARTRIDGE_OUT` (bit 90) |
| Pump hardware error | Internal pump failure | Multiple bit indices |

### Cartridge Lifetime

- **Maximum duration:** 3 days (72 hours) from insertion
- **Tracking:** Insertion time stored via `writeCartridgeInsertionDate` (char `0x210B`)
- **Expiry alerts:** 12 hours, 6 hours, and 2 hours before the 72-hour mark
- **Expiry alarm:** At 72 hours — pump stops, cartridge must be replaced

---

## 18. Error Handling & Recovery

### Write Timeout Monitoring

BLE write latency should be monitored. If a characteristic write takes longer than **700 ms**, this indicates BLE congestion or range issues.

```java
long elapsed = System.currentTimeMillis() - startTime;
if (elapsed > 700) {
    log.warn("Characteristic write succeeded but slow",
             "durationMillis", elapsed);
}
```

### Connection State Atomicity

State transitions in `KldPumpDataSource` are guarded by atomic compare-and-set on the `MutableStateFlow<ConnectionState>`. The `changeState(old, new)` method only transitions if the current state matches `old`, preventing race conditions during reconnection.

### Notification Parser Error Handling

Every notification parser class follows a strict pattern:
1. Check `data.length == DATA_SIZE` — return `ParsingFailureMessage` if wrong size
2. Parse byte(s) to enum/value — return `ParsingFailureMessage` if value is unknown
3. Only create typed message on success

The `KldPumpDataSource` logs parsed messages differently:
- **Success:** `KLD__DATASOURCE__PUSH_RECEIVED` with UUID, raw hex, parsed type, parsed object
- **Unknown UUID:** `KLD__DATASOURCE__PUSH_UNKNOWN_MESSAGE`
- **Parse failure:** `KLD__DATASOURCE__PUSH_PARSING_FAILED` (logged as error)

All messages (including failures) are emitted to `messageSharedFlow` for downstream consumers.

### Alarm Recovery

When the pump enters an alarm state (`KldIduMode.ALARM`):
1. Read unacknowledged alarms via `readUnacknowledgedAlarms()`
2. Present alarm information to user
3. Acknowledge alarms via `acknowledgeAlarm(Set<KldAlarm>)` — write 18-byte bitset to `0x2103`
4. Monitor `KldIduMode` notification for return to `DELIVERY` or `IDLE`

Some alarms are **non-recoverable** (hardware failures) — the pump must be physically replaced.

### BLE Disconnection Recovery

On unexpected disconnection:
1. The `onConnectionStateChange` handler detects `GattConnectionState.STATE_DISCONNECTED`
2. State transitions to `DISCONNECTED`
3. Coroutine scope is cancelled
4. The pump continues autonomous basal delivery (the last programmed profile runs independently)
5. Reconnection requires full `connect()` → service discovery → notification registration → unlock sequence

> **Critical:** The pump delivers its programmed basal profile autonomously. BLE disconnection does NOT stop insulin delivery. Only `updateDelivery(STOPPED)` or `shutdownPump()` halts delivery.

---

## 19. Implementation Notes

### BLE Write Type

All characteristic writes use `BleWriteType.DEFAULT` which maps to Android's `BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT` — this is a **Write Request** (with acknowledgement). The pump sends a BLE Write Response for every write, ensuring delivery confirmation at the BLE layer.

### CCCD Subscription

Notification characteristics require Client Characteristic Configuration Descriptor (CCCD) subscription. The UUID for CCCD is the standard BLE UUID:
```
00002902-0000-1000-8000-00805f9b34fb
```

The Nordic BLE library handles CCCD subscription automatically when collecting notification flows. For a raw BLE implementation, you must write `0x01 0x00` (enable notifications) to the CCCD descriptor of each notify characteristic.

### Characteristic Discovery

Characteristics are discovered dynamically after GATT service discovery. The `characteristicMap` (`Map<String, ClientBleGattCharacteristic>`) is populated by iterating `service.characteristics` and keying by UUID string. All subsequent reads/writes use this map.

### Concurrency Model

BLE operations should be serialized using coroutines or equivalent:
- Each BLE operation (`writeCharacteristic`, `readCharacteristic`) is a suspend function
- Operations are NOT parallelized — they are sequential within the caller's coroutine
- A single `CoroutineScope` tied to the connection lifetime manages all BLE operations
- Disconnection cancels this scope, aborting any in-flight operations

### Service UUID Discovery

The BLE service UUID is not hardcoded — it is discovered by iterating GATT services after connection. The `ClientBleGattService` object exposes the UUID. Based on the characteristic UUID pattern (`812321XX-5ea1-589e-004d-6548f98fc73c`), the service UUID is expected to follow the same base pattern.

For implementation, discover services and look for the service containing characteristics with the `812321XX` prefix.

### Thread Safety

- Connection state (`_stateFlow`) uses `MutableStateFlow` with atomic operations
- Message notifications (`_messageSharedFlow`) use `MutableSharedFlow` (thread-safe emit)
- BLE writes should be serialized — do not issue concurrent writes to different characteristics

---

## Appendix A: Complete Characteristic UUID Quick Reference

```
SERVICE:  812321XX-5ea1-589e-004d-6548f98fc73c

CHAR  HEX   DIRECTION   PURPOSE
─────────────────────────────────────────────────
2100  R/W/N  IDU Mode (read/notify), Shutdown (write)
2101  R/N    Alarm Status
2103  W      Acknowledge Alarm
2104  R/W/N  Reservoir Level
2105  R/W/N  Delivery State
2107  W      Basal Profile
2108  W      Temp Basal Request
2109  R/N    Temp Basal Time Left
210A  W      Bolus Request
210B  R/W/N  Cartridge Insertion Date
210C  R/N    Delivery Type
210E  N      Pump Event
2111  W      Insulin On Board (reset)
2112  R/N    Current Basal Rate
2113  W      Prime Pump
2114  W      Exclusive Connection
2115  W      Total Daily Dose (reset)
2117  R/W    System Time
2118  W      Command Channel (ring/pair/unlock)
2A19  R/N    Battery Level (BLE standard)
```

## Appendix B: Wire Format Quick Reference

```
BOLUS REQUEST (0x210A) — 6 bytes:
  [amount_u16_LE] [0x00 0x00] [0x00 0x00]

TEMP BASAL (0x2108) — 4 bytes:
  [percentage_u16_LE] [duration_u16_LE]

SYSTEM TIME (0x2117) — 9 bytes:
  [year_u16_LE] [month] [day] [hours] [min] [sec] [tci] [roc]

BASAL PROFILE (0x2107) — 44 bytes:
  ["SECURITY_BASAL_PROFI" padded to 20] [rate_0 .. rate_23]

RESERVOIR LEVEL (0x2104) — 2 bytes:
  [level_in_pulses_u16_LE]

COMMAND PACKET (0x2118) — variable:
  [cmd_id_byte] [payload_bytes...]
  
  cmd_id=0x01: StorePairingKey  (payload: 16 zero bytes)
  cmd_id=0x02: ClearPairingKey  (payload: 16 zero bytes)
  cmd_id=0x03: Ring             (payload: variable)
  cmd_id=0x05: UnlockPump       (payload: "OTOphaYROmOgYMER")

DELIVERY STATE (0x2105) — 1 byte:
  0=UNDEFINED, 1=STOPPED, 2=PAUSED, 3=PRIMING, 4=DELIVERING

IDU MODE (0x2100) — 1 byte:
  0=BOOT, 1=IDLE, 2=ALARM, 3=DELIVERY, 4=SHUTDOWN

PRIME PUMP (0x2113) — 1 byte:
  [number_of_pulses]

EXCLUSIVE CONNECTION (0x2114) — 1 byte:
  [0x01]

SHUTDOWN (0x2100 write) — 1 byte:
  [0x04]

ALARM ACK (0x2103) — 18 bytes:
  [bitfield, LSB-first, bit = alarm.bitIndex + 6]
```

---

*Document generated from reverse-engineered sources and the official Kaleido Guidebook.*
