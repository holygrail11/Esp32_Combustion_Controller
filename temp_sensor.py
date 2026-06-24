"""
temp_sensor.py
MAX6675 K-type thermocouple SPI driver for MicroPython (ESP32).

Wiring:
    MAX6675 SCK  -> GPIO 18
    MAX6675 CS   -> GPIO 5
    MAX6675 SO   -> GPIO 19
    MAX6675 VCC  -> 3.3V
    MAX6675 GND  -> GND

    Also pick any unused GPIO as a dummy MOSI pin (e.g. GPIO 2).
    It is never driven but SoftSPI requires the argument.

Usage:
    from temp_sensor import MAX6675
    sensor = MAX6675(sck=18, cs=5, so=19, dummy_mosi=2)
    temp = sensor.read_celsius()
"""

from machine import Pin, SoftSPI
import time


class MAX6675:
    """
    Driver for the MAX6675 cold-junction-compensated K-type thermocouple.

    The MAX6675 is read-only SPI (CPOL=0, CPHA=0).
    It returns a 16-bit word:
        Bits 14:3  -> 12-bit temperature (0.25 C per LSB)
        Bit  2     -> device ID (always 0)
        Bit  1     -> open-circuit fault flag
        Bit  0     -> unused
    Conversion time is ~170 ms so we throttle reads to 250 ms minimum.
    """

    CONVERSION_TIME_MS = 250

    def __init__(self, sck, cs, so, dummy_mosi=2):
        self._cs = Pin(cs, Pin.OUT, value=1)

        # dummy_mosi is required by SoftSPI but MAX6675 never uses MOSI.
        # Pick any GPIO that is not connected to anything on your board.
        self._spi = SoftSPI(
            baudrate=100_000,
            polarity=0,
            phase=0,
            sck=Pin(sck),
            mosi=Pin(dummy_mosi),
            miso=Pin(so),
        )

        self._last_read_ms = 0
        self._last_temp_c  = 0.0
        self._fault        = False

    def read_celsius(self):
        now     = time.ticks_ms()
        elapsed = time.ticks_diff(now, self._last_read_ms)
        if elapsed < self.CONVERSION_TIME_MS:
            return self._last_temp_c

        raw = self._read_raw()
        self._last_read_ms = time.ticks_ms()

        # Check for communication failure (all zeros)
        if raw == 0x0000:
            print("[DEBUG] MAX6675: SPI communication failure (raw=0x0000)")
            self._fault = True
            raise RuntimeError("MAX6675: SPI communication failure or no thermocouple attached")

        if raw & 0x0004:
            self._fault = True
            raise RuntimeError("MAX6675: thermocouple open-circuit")

        self._fault       = False
        raw_temp          = (raw >> 3) & 0x0FFF
        self._last_temp_c = raw_temp * 0.25
        return self._last_temp_c

    def read_fahrenheit(self):
        return self.read_celsius() * 9 / 5 + 32

    @property
    def fault(self):
        return self._fault

    def _read_raw(self):
        buf = bytearray(2)
        self._cs.value(0)
        time.sleep_us(10)  # Increase delay before read
        self._spi.readinto(buf)
        time.sleep_us(10)  # Increase delay after read
        self._cs.value(1)
        time.sleep_us(100)  # Allow settling time between reads
        
        raw = (buf[0] << 8) | buf[1]
        
        # Debug: print raw bytes to diagnose
        print("[DEBUG] MAX6675 raw value: 0x{:04x} (bytes: 0x{:02x} 0x{:02x})".format(raw, buf[0], buf[1]))
        
        return raw
