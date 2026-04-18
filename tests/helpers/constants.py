"""Kaleido BLE protocol constants — UUIDs, tokens, enumerations, operational limits.

All values are derived from the Kaleido Pump Technical Manual sections §3, §4, §7,
§11, §13, §14, §16, and §17.
"""

# ---------------------------------------------------------------------------
# UUID helpers
# ---------------------------------------------------------------------------
_BASE = "8123{:04x}-5ea1-589e-004d-6548f98fc73c"

# Service UUID — runtime-discovered; base-pattern derivation per §4 / §19
SERVICE_UUID = _BASE.format(0x2100)  # likely 81232100-5ea1-589e-004d-6548f98fc73c
SERVICE_UUID_PREFIX = "812321"

# ---------------------------------------------------------------------------
# Characteristic UUIDs  (§4 / Appendix A)
# ---------------------------------------------------------------------------

# Read / Notify
CHAR_IDU_MODE             = _BASE.format(0x2100)  # R/W/N
CHAR_ALARM_STATUS         = _BASE.format(0x2101)  # R/N
CHAR_RESERVOIR_LEVEL      = _BASE.format(0x2104)  # R/W/N
CHAR_DELIVERY_STATE       = _BASE.format(0x2105)  # R/W/N
CHAR_TEMP_BASAL_TIME_LEFT = _BASE.format(0x2109)  # R/N
CHAR_CARTRIDGE_DATE       = _BASE.format(0x210B)  # R/W/N
CHAR_DELIVERY_TYPE        = _BASE.format(0x210C)  # R/N
CHAR_PUMP_EVENT           = _BASE.format(0x210E)  # N
CHAR_CURRENT_BASAL_RATE   = _BASE.format(0x2112)  # R/N
CHAR_BATTERY_LEVEL        = "00002a19-0000-1000-8000-00805f9b34fb"  # standard BLE SIG

# Write-only
CHAR_ALARM_ACK            = _BASE.format(0x2103)  # W
CHAR_BASAL_PROFILE        = _BASE.format(0x2107)  # W
CHAR_TEMP_BASAL_REQUEST   = _BASE.format(0x2108)  # W
CHAR_BOLUS_REQUEST        = _BASE.format(0x210A)  # W
CHAR_INSULIN_ON_BOARD     = _BASE.format(0x2111)  # W
CHAR_PRIME_PUMP           = _BASE.format(0x2113)  # W
CHAR_EXCLUSIVE_CONNECTION = _BASE.format(0x2114)  # W
CHAR_TOTAL_DAILY_DOSE     = _BASE.format(0x2115)  # W
CHAR_SYSTEM_TIME          = _BASE.format(0x2117)  # R/W
CHAR_COMMAND_CHANNEL      = _BASE.format(0x2118)  # W  (ring / pair / unlock)

# Complete set of all 20 characteristic UUIDs (for §4 discovery tests)
ALL_CHARACTERISTIC_UUIDS: frozenset[str] = frozenset({
    CHAR_IDU_MODE,
    CHAR_ALARM_STATUS,
    CHAR_RESERVOIR_LEVEL,
    CHAR_DELIVERY_STATE,
    CHAR_TEMP_BASAL_TIME_LEFT,
    CHAR_CARTRIDGE_DATE,
    CHAR_DELIVERY_TYPE,
    CHAR_PUMP_EVENT,
    CHAR_CURRENT_BASAL_RATE,
    CHAR_BATTERY_LEVEL,
    CHAR_ALARM_ACK,
    CHAR_BASAL_PROFILE,
    CHAR_TEMP_BASAL_REQUEST,
    CHAR_BOLUS_REQUEST,
    CHAR_INSULIN_ON_BOARD,
    CHAR_PRIME_PUMP,
    CHAR_EXCLUSIVE_CONNECTION,
    CHAR_TOTAL_DAILY_DOSE,
    CHAR_SYSTEM_TIME,
    CHAR_COMMAND_CHANNEL,
})

# ---------------------------------------------------------------------------
# BLE descriptors
# ---------------------------------------------------------------------------
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

# ---------------------------------------------------------------------------
# Security (§14)
# ---------------------------------------------------------------------------
UNLOCK_TOKEN = "OTOphaYROmOgYMER"
UNLOCK_TOKEN_BYTES: bytes = UNLOCK_TOKEN.encode("ascii")  # 16 bytes

# ---------------------------------------------------------------------------
# Command IDs (§7)
# ---------------------------------------------------------------------------
CMD_STORE_PAIRING_KEY: int = 0x01
CMD_CLEAR_PAIRING_KEY: int = 0x02
CMD_RING:              int = 0x03
CMD_UNLOCK_PUMP:       int = 0x05

# Ring payload — 16-byte fixed beep pattern (§7 / §8.15)
RING_PAYLOAD: bytes = bytes([
    0x0F, 0x07, 0x0F, 0x07, 0x0F, 0x07, 0x0F,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])

# ---------------------------------------------------------------------------
# Enumerations (§11)
# ---------------------------------------------------------------------------

# KldIduMode
IDU_MODE: dict[str, int] = {
    "BOOT":     0,
    "IDLE":     1,
    "ALARM":    2,
    "DELIVERY": 3,
    "SHUTDOWN": 4,
}
IDU_MODE_BY_VALUE: dict[int, str] = {v: k for k, v in IDU_MODE.items()}
VALID_IDU_MODES: frozenset[int] = frozenset(IDU_MODE.values())

# KldDeliveryState
DELIVERY_STATE: dict[str, int] = {
    "UNDEFINED":  0,
    "STOPPED":    1,
    "PAUSED":     2,
    "PRIMING":    3,
    "DELIVERING": 4,
}
DELIVERY_STATE_BY_VALUE: dict[int, str] = {v: k for k, v in DELIVERY_STATE.items()}
VALID_DELIVERY_STATES: frozenset[int] = frozenset(DELIVERY_STATE.values())

# KldDeliveryType — single-byte bitmask
DELIVERY_TYPE_BASAL:      int = 0x01
DELIVERY_TYPE_TEMP_BASAL: int = 0x02
DELIVERY_TYPE_BOLUS:      int = 0x04

# ConnectionState
CONNECTION_STATE: dict[str, int] = {
    "DISCONNECTED":                        0,
    "CONNECTING":                          1,
    "CONNECTED_REGISTERING_STATE_CHANGES": 2,
    "CONNECTED_DISCOVERING_SERVICES":      3,
    "CONNECTED_REGISTERING_PUSH":          4,
    "CONNECTED_AVAILABLE":                 5,
    "DISCONNECTING":                       6,
    "PENDING_UNLOCK":                      7,
}

# ---------------------------------------------------------------------------
# Operational limits (§3)
# ---------------------------------------------------------------------------

# Conversion factor
PULSE_TO_UNITS: float = 0.05  # 1 pulse = 0.05 U

# Basal rate
BASAL_RATE_MIN_UHR:     float = 0.05
BASAL_RATE_MAX_UHR:     float = 5.00
BASAL_RATE_INCREMENT:   float = 0.05
BASAL_RATE_MIN_BYTE:    int   = 1
BASAL_RATE_MAX_BYTE:    int   = 100
BASAL_PROFILE_SEGMENTS: int   = 24
BASAL_PROFILE_NAME:     str   = "SECURITY_BASAL_PROFI"
BASAL_PROFILE_NAME_SIZE: int  = 20
BASAL_PROFILE_SIZE:     int   = 24   # 24 hourly rate bytes

# Bolus
BOLUS_MIN_PULSES: int   = 1     # 0.05 U
BOLUS_MAX_PULSES: int   = 400   # 20.00 U
BOLUS_MIN_UNITS:  float = 0.05
BOLUS_MAX_UNITS:  float = 20.00

# Temporary basal
TEMP_BASAL_MIN_PCT:      int = 0
TEMP_BASAL_MAX_PCT:      int = 200
TEMP_BASAL_MIN_DURATION: int = 30    # minutes (0.5 h)
TEMP_BASAL_MAX_DURATION: int = 1440  # minutes (24 h)

# Reservoir
RESERVOIR_MAX_PULSES: int = 4000  # 200 U

# Cartridge lifetime
CARTRIDGE_LIFETIME_HOURS: int = 72

# Alert thresholds (§17)
BATTERY_ALERT_THRESHOLDS_PCT:   list[int] = [25, 10, 5]
RESERVOIR_ALERT_THRESHOLDS_U:   list[int] = [50, 25, 5]
CARTRIDGE_EXPIRY_ALERT_HOURS:   list[int] = [12, 6, 2]  # hours before expiry

# ---------------------------------------------------------------------------
# Notification DATA_SIZE constants (§10)
# ---------------------------------------------------------------------------
NOTIFICATION_DATA_SIZE: dict[str, int] = {
    CHAR_IDU_MODE:             1,
    CHAR_ALARM_STATUS:         20,
    CHAR_RESERVOIR_LEVEL:      2,
    CHAR_DELIVERY_STATE:       1,
    CHAR_TEMP_BASAL_TIME_LEFT: 2,
    CHAR_CARTRIDGE_DATE:       2,   # RemainingBolusMessage (§10, 0x210B → 2 bytes)
    CHAR_DELIVERY_TYPE:        1,
    CHAR_CURRENT_BASAL_RATE:   2,
    CHAR_BATTERY_LEVEL:        1,
    CHAR_SYSTEM_TIME:          9,
}

# ---------------------------------------------------------------------------
# Alarm bit indices (§13) — all 74 KldAlarm enum values
# ---------------------------------------------------------------------------
ALARM_BIT_INDICES: dict[str, int] = {
    # Critical / hardware
    "ERROR_POF_VCC_NRF_LOW":                            0,
    "ERROR_ADC_10V_HIGH":                               2,
    "ERROR_ADC_10V_LOW":                                3,
    "ERROR_PUMP_CONSTANT_CURRENT_FAILURE":              4,
    "ERROR_PUMP_BOOTLOADER_NOT_CONFIGURED":             5,
    "ERROR_PUMP_ACTUATOR_NOT_POWERFUL_ENOUGH":          6,
    "ERROR_PUMP_ALARM_1006_NOT_COMPLETED_BEFORE_PULSE": 7,
    # Battery & consumables
    "ERROR_PUMP_ALARM_BATTERY_FLAT":                    10,
    "ERROR_PUMP_ALARM_RESERVOIR_EMPTY":                 11,
    "ERROR_PUMP_ALARM_CARTRIDGE_EXPIRED":               12,
    "ERROR_PUMP_ALERT_BATTERY_LEVEL_ALERT":             13,
    "ERROR_PUMP_ALERT_RESERVOIR_LEVEL_ALERT":           14,
    "ERROR_PUMP_ALERT_CARTRIDGE_EXPIRING_SOON":         15,
    # Occlusion & delivery
    "ERROR_PUMP_OCCLUSION":                             16,
    "ERROR_PUMP_PULSE_PRECONDITION_FAIL":               30,
    "ERROR_PUMP_IMPOSSIBLE_EXTENDED_BOLUS":             31,
    # Memory
    "ERROR_FRAM_WRITE_FAIL":                            20,
    "ERROR_FRAM_READ_FAIL":                             21,
    "ERROR_FRAM_INVALID_OPERATION":                     22,
    "ERROR_PUMP_PSM_GETRESULT_BLOCKED":                 23,
    # POST failures
    "ERROR_POST_PROCESSOR_REG_FAIL":                    40,
    "ERROR_POST_PROCESSOR_FLAGS_FAIL":                  41,
    "ERROR_POST_PROCESSOR_INSTRUCTION_FAIL":            42,
    "ERROR_POST_CLOCK_FREQ_FAIL":                       45,
    "ERROR_POST_RAM_ADDRESS_FAIL":                      46,
    "ERROR_POST_RAM_AA_FAIL":                           47,
    "ERROR_POST_RAM_55_FAIL":                           48,
    "ERROR_POST_RAM_RESULT_FAIL":                       49,
    # Occlusion sensor
    "ERROR_OCCLUSION_SENSOR_FAILED_TO_INITIALISE":      52,
    "ERROR_OCCLUSION_I2C_FAILURE":                      55,
    "ERROR_OCCLUSION_VALUE_FAILED_TO_STABILIZE":        56,
    # System
    "ERROR_PUMP_BLE_INITIALISATION":                    61,
    "ERROR_PUMP_UNEXPECTED_RESET":                      70,
    "ERROR_PUMP_HARDWARE_WATCHDOG_PIN_RESET":           71,
    "ERROR_PUMP_HARDFAULT":                             72,
    "ERROR_PUMP_NMI":                                   73,
    "ERROR_PUMP_CPULOCKUP":                             74,
    "ERROR_PUMP_UNEXPECTED_SW_RESET":                   75,
    "ERROR_PUMP_ASSERT":                                76,
    # NRF rejections
    "ERROR_PUMP_NRF_IDU_MODE_REJECTED":                 77,
    "ERROR_PUMP_NRF_DELIVERY_STATE_REJECTED":           78,
    "ERROR_PUMP_NRF_BASAL_PROFILE_REJECTED":            79,
    "ERROR_PUMP_NRF_ALARM_ACK_REJECTED":                80,
    "ERROR_PUMP_NRF_PRIMING_DATA_REJECTED":             81,
    "ERROR_PUMP_BOLUS_REJECTED":                        82,
    "ERROR_PUMP_TEMPORARY_BASAL_REJECTED":              83,
    "ERROR_PUMP_UNEXPECTED_PULSE":                      84,
    "ERROR_PUMP_PSM_CRC_FAIL":                          85,
    # Other
    "ERROR_PUMP_CARTRIDGE_OUT":                         90,
    "ERROR_PUMP_UNEXPECTED_SHUTDOWN":                   91,
    "ERROR_PUMP_WITH_NORDIC_PROCESSOR":                 92,
    "ERROR_PUMP_WHEN_WRITING_PUMP_EVENT":               93,
    "ERROR_PUMP_INVALID_PERSISTENT_MEMORY_VERSION":     94,
    "ERROR_PUMP_ERASED_PERSISTENT_MEMORY":              95,
    # RTC & driver failures
    "ERROR_PUMP_RTC_COUNTER_FAIL":                      100,
    "ERROR_PUMP_RTC_OFFSET_FAIL":                       101,
    "ERROR_PUMP_RTC_FREQ_FAIL_LO":                      102,
    "ERROR_PUMP_RTC_FREQ_FAIL":                         103,
    "ERROR_PUMP_TIMER_DRIVER_FAIL":                     111,
    "ERROR_PUMP_PERIPHERAL_INTERFACE_FAIL":             112,
    "ERROR_PUMP_ONE_SHOT_TIMER_FAIL":                   113,
    "ERROR_PUMP_RTC_FAIL":                              114,
    "ERROR_PUMP_SUPPLY_HOLD_FAIL":                      115,
    "ERROR_PUMP_UART_INIT_FAIL":                        116,
    "ERROR_PUMP_BLE_PERIPH_DRIVER_FAIL":                117,
    "ERROR_PUMP_I2C_DRIVER_INIT_FAIL":                  118,
    "ERROR_PUMP_AUDIO_DRIVER_INIT_FAIL":                119,
    "ERROR_PUMP_PUMP_ACTUATOR_DRIVER_FAIL":             120,
    "ERROR_PUMP_GAS_GAUGE_DRIVER_FAIL":                 121,
    "ERROR_PUMP_FRAM_DRIVER_FAIL":                      122,
    "ERROR_PUMP_FAULT_LED_DRIVER_FAIL":                 123,
    "ERROR_PUMP_POWER_ON_DRIVER_FAIL":                  124,
    "ERROR_PROXIMITY_SENSOR_DRIVER_FAIL":               125,
    "ERROR_ALARM_DEFINITION_MISMATCH_PUMP":             137,
}
ALARM_BIT_INDICES_BY_VALUE: dict[int, str] = {v: k for k, v in ALARM_BIT_INDICES.items()}
