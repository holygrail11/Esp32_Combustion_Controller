"""
fan_control.py
Fan on/off GPIO driver for MicroPython on ESP32.

The 8025HSL fan runs at 12V — use a relay module, NPN transistor,
or MOSFET. Do NOT connect the fan directly to an ESP32 GPIO.

active_low=True  -> relay module (LOW = fan ON)
active_low=False -> transistor / MOSFET (HIGH = fan ON)

Wiring (relay module):
    Relay IN  -> GPIO 14
    Relay VCC -> 3.3V or 5V (check your module)
    Relay GND -> GND
    Relay COM -> 12V +
    Relay NO  -> Fan + (red wire)
    Fan GND   -> 12V -

Usage:
    from fan_control import Fan
    fan = Fan(pin=14, active_low=True)
    fan.on()
    fan.off()
    fan.set(True)
"""

from machine import Pin


class Fan:

    def __init__(self, pin, active_low=False):
        self._active_low = active_low
        self._pin        = Pin(pin, Pin.OUT)
        self._state      = False
        self.off()

    def on(self):
        self._state = True
        self._pin.value(0 if self._active_low else 1)

    def off(self):
        self._state = False
        self._pin.value(1 if self._active_low else 0)

    def set(self, state):
        if state:
            self.on()
        else:
            self.off()

    @property
    def is_on(self):
        return self._state
