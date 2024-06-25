"""
smoke_sensor.py
Analog smoke / air-quality sensor driver for MicroPython on ESP32.

Works with MQ-2, MQ-135, and similar analog sensors.
ESP32 ADC reads 0-3.3V, returns 12-bit value (0-4095).

Wiring:
    MQ-2 A0   -> GPIO 34  (use ADC1 pins: 32-39; avoid ADC2 which shares with WiFi)
    MQ-2 VCC  -> 5V
    MQ-2 GND  -> GND

    The sensor heater needs ~60s warm-up before readings are stable.

Usage:
    from smoke_sensor import SmokeSensor
    sensor = SmokeSensor(pin=34)
    raw    = sensor.read_raw()      # 0-4095
    level  = sensor.classify()      # "normal", "high", or "critical"
"""

from machine import Pin, ADC
import time

THRESHOLD_HIGH     = 500
THRESHOLD_CRITICAL = 900
SAMPLE_COUNT       = 8
READ_INTERVAL_MS   = 100


class SmokeSensor:

    def __init__(self, pin=34, threshold_high=THRESHOLD_HIGH,
                 threshold_critical=THRESHOLD_CRITICAL, sample_count=SAMPLE_COUNT):

        # Works on all MicroPython ESP32 versions
        self._adc = ADC(Pin(pin))
        self._adc.atten(ADC.ATTN_11DB)

        self.threshold_high     = threshold_high
        self.threshold_critical = threshold_critical
        self._sample_count      = sample_count
        self._last_read_ms      = 0
        self._cached_raw        = 0

    def read_raw(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_read_ms) >= READ_INTERVAL_MS:
            total = sum(self._adc.read() for _ in range(self._sample_count))
            self._cached_raw   = total // self._sample_count
            self._last_read_ms = time.ticks_ms()
        return self._cached_raw

    def read_percent(self):
        return (self.read_raw() / 4095.0) * 100.0

    def classify(self):
        raw = self.read_raw()
        if raw > self.threshold_critical:
            return "critical"
        elif raw > self.threshold_high:
            return "high"
        else:
            return "normal"
