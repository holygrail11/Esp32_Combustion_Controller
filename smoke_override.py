"""
smoke_override.py
Smoke override layer — sits on top of zone_logic temperature output.

Rules:
    Normal   (0-500):   keep base angle, buzzer off
    High   (501-900):   base + 20 degrees, buzzer on
    Critical  (>900):   force 90 degrees, buzzer on

Final angle is always clamped to SERVO_MAX_ANGLE (90).

Wiring:
    Buzzer signal -> GPIO 27
    Buzzer GND    -> GND

Usage:
    from smoke_override import SmokeOverride
    from smoke_sensor   import SmokeSensor
    sensor   = SmokeSensor(pin=34)
    override = SmokeOverride(buzzer_pin=27)
    final_angle, buzzer_on = override.apply(base_angle=30, sensor=sensor)
"""

from machine import Pin
from smoke_sensor import SmokeSensor

SMOKE_HIGH_EXTRA_DEGREES = 20
SMOKE_CRITICAL_ANGLE     = 90
SERVO_MAX_ANGLE          = 90


class SmokeOverride:

    def __init__(self, buzzer_pin, active_low=False):
        self._active_low = active_low
        self._buzzer     = Pin(buzzer_pin, Pin.OUT)
        self._buzzer_on  = False
        self._set_buzzer(False)

    def apply(self, base_angle, sensor):
        """
        Returns (final_angle, buzzer_on).
        base_angle: servo angle from zone_logic
        sensor: SmokeSensor instance
        """
        level = sensor.classify()

        if level == "critical":
            final_angle = SMOKE_CRITICAL_ANGLE
            buzzer_on   = True
        elif level == "high":
            final_angle = base_angle + SMOKE_HIGH_EXTRA_DEGREES
            buzzer_on   = True
        else:
            final_angle = base_angle
            buzzer_on   = False

        # Hard clamp — never exceed physical servo limit
        final_angle = min(final_angle, SERVO_MAX_ANGLE)

        self._set_buzzer(buzzer_on)
        self._buzzer_on = buzzer_on

        return final_angle, buzzer_on

    def silence(self):
        self._set_buzzer(False)
        self._buzzer_on = False

    @property
    def buzzer_active(self):
        return self._buzzer_on

    def get_smoke_label(self, sensor):
        raw   = sensor.read_raw()
        level = sensor.classify()
        if level == "critical":
            return "Smk:{:4d} CRIT! ".format(raw)
        elif level == "high":
            return "Smk:{:4d} HIGH  ".format(raw)
        else:
            return "Smk:{:4d} OK    ".format(raw)

    def _set_buzzer(self, on):
        if self._active_low:
            self._buzzer.value(0 if on else 1)
        else:
            self._buzzer.value(1 if on else 0)
