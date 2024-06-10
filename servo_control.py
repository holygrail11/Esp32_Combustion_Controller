"""
servo_control.py
MG996R servo motor driver for MicroPython on ESP32.

Standard PWM servo:
    Period   : 20ms (50Hz)
    0 deg    : ~1.0ms pulse
    90 deg   : ~1.5ms pulse
    180 deg  : ~2.0ms pulse

Wiring:
    MG996R signal (orange) -> GPIO 13
    MG996R VCC    (red)    -> 5V from external supply (NOT ESP32 pin)
    MG996R GND    (brown)  -> GND shared with ESP32

    The MG996R draws up to 2.5A stall. Use a dedicated 5V supply.

Usage:
    from servo_control import Servo
    servo = Servo(pin=13)
    servo.set_angle(90)
"""

from machine import Pin, PWM
import time


class Servo:

    FREQUENCY_HZ = 50
    MIN_PW_US    = 1000   # 0 degrees
    MAX_PW_US    = 2000   # 180 degrees
    SETTLE_MS    = 400    # time for servo to physically reach position

    def __init__(self, pin):
        self._pwm           = PWM(Pin(pin), freq=self.FREQUENCY_HZ)
        self._current_angle = -1
        self.set_angle(0)

    def set_angle(self, angle, wait=True):
        if not 0 <= angle <= 180:
            raise ValueError("Servo angle must be 0-180, got {}".format(angle))

        if angle == self._current_angle:
            return

        duty_ns = self._angle_to_duty_ns(angle)
        self._pwm.duty_ns(duty_ns)
        self._current_angle = angle

        if wait:
            time.sleep_ms(self.SETTLE_MS)

    def detach(self):
        """Stop PWM output to prevent jitter when idle."""
        self._pwm.duty_ns(0)

    @property
    def current_angle(self):
        return self._current_angle

    def _angle_to_duty_ns(self, angle):
        pw_us = self.MIN_PW_US + (angle / 180.0) * (self.MAX_PW_US - self.MIN_PW_US)
        return int(pw_us * 1000)
