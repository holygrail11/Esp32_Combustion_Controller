"""
lcd_display.py
I2C LCD driver for MicroPython on ESP32.
HD44780 controller with PCF8574 I2C backpack (common 16x2 / 20x4 panels).

Default address 0x27. Try 0x3F if display stays blank.
To scan: i2c.scan() should return [39] (0x27) or [63] (0x3F).

Wiring:
    LCD SDA -> GPIO 21
    LCD SCL -> GPIO 22
    LCD VCC -> 5V
    LCD GND -> GND

Usage:
    from lcd_display import LCD
    lcd = LCD(sda=21, scl=22)
    lcd.clear()
    lcd.write(0, "Hello")
    lcd.write(1, "World")
"""

from machine import I2C, Pin
import time

_RS  = 0x01
_EN  = 0x04
_BL  = 0x08

_CMD_CLEAR       = 0x01
_CMD_HOME        = 0x02
_CMD_ENTRY_MODE  = 0x06
_CMD_DISPLAY_ON  = 0x0C
_CMD_4BIT_2LINE  = 0x28
_CMD_SET_DDRAM   = 0x80

_ROW_OFFSETS = (0x00, 0x40, 0x14, 0x54)


class LCD:

    def __init__(self, sda=21, scl=22, i2c_address=0x27,
                 cols=16, rows=2, freq=400_000):
        self._i2c  = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=freq)
        self._addr = i2c_address
        self._cols = cols
        self._rows = rows
        self._bl   = _BL
        self._init_display()

    def clear(self):
        self._cmd(_CMD_CLEAR)
        time.sleep_ms(2)

    def home(self):
        self._cmd(_CMD_HOME)
        time.sleep_ms(2)

    def write(self, row, text, col=0):
        if not 0 <= row < self._rows:
            return
        available = self._cols - col
        # Pad/truncate to fill the row so old characters are overwritten
        text = text[:available].ljust(available)
        self._set_cursor(row, col)
        for char in text:
            code = ord(char)
            if not (0x20 <= code <= 0x7E):
                code = ord("?")
            self._data(code)

    def backlight(self, on):
        self._bl = _BL if on else 0x00
        self._write_i2c(self._bl)

    def _init_display(self):
        time.sleep_ms(50)
        for _ in range(3):
            self._write4(0x03 << 4)
            time.sleep_ms(5)
        self._write4(0x02 << 4)
        time.sleep_us(100)
        for cmd in (_CMD_4BIT_2LINE, _CMD_DISPLAY_ON, _CMD_CLEAR, _CMD_ENTRY_MODE):
            self._cmd(cmd)
        time.sleep_ms(2)

    def _set_cursor(self, row, col):
        self._cmd(_CMD_SET_DDRAM | (_ROW_OFFSETS[row] + col))

    def _cmd(self, value):
        self._send(value, rs=False)

    def _data(self, value):
        self._send(value, rs=True)

    def _send(self, value, rs):
        rs_bit     = _RS if rs else 0x00
        high_nibble = (value & 0xF0) | rs_bit
        low_nibble  = ((value << 4) & 0xF0) | rs_bit
        self._write4(high_nibble)
        self._write4(low_nibble)

    def _write4(self, nibble):
        base = nibble | self._bl
        self._write_i2c(base | _EN)
        time.sleep_us(1)
        self._write_i2c(base & ~_EN)
        time.sleep_us(50)

    def _write_i2c(self, value):
        self._i2c.writeto(self._addr, bytes([value]))
