"""
zone_logic.py
Temperature zone classifier.

Zone table:
    Zone 1   0-70  C   servo  0   fan ON    heat retention
    Zone 2  71-130 C   servo 30   fan ON    normal combustion
    Zone 3 131-170 C   servo 60   fan OFF   moderate airflow
    Zone 4 171-200 C   servo 90   fan OFF   maximum cooling

Usage:
    from zone_logic import get_zone, zone_changed
    result = get_zone(145.0)
    print(result[2], result[3])   # servo_angle, fan_on
"""

# Each zone is a tuple:
# (max_temp, servo_angle, fan_on, label, purpose)
_ZONES = (
    ( 70.0,  0, True,  "Zone 1  0-70C ",  "Heat retention "),
    (130.0, 30, True,  "Zone 2 71-130C",  "Normal combustn"),
    (170.0, 60, False, "Zone 3 131-170",  "Moderate airflw"),
    (200.0, 90, False, "Zone 4 171-200",  "Max cooling    "),
)

# Indices into the tuple (avoids namedtuple for MicroPython compatibility)
ZONE_NUMBER  = 0   # not stored in tuple — set in get_zone return value
ZONE_MAXT    = 0
ZONE_ANGLE   = 1
ZONE_FAN     = 2
ZONE_LABEL   = 3
ZONE_PURPOSE = 4

# Safe defaults when out of range
_OVER_RANGE  = (0, 90, False, "!! OVER RANGE !!", "Check sensor   ")
_UNDER_RANGE = (0,  0, True,  "BELOW RANGE     ", "Sensor fault?  ")


def get_zone(temp_c):
    """
    Returns a tuple: (zone_number, servo_angle, fan_on, label, purpose)
    zone_number is 1-4, or 0 if out of range.
    """
    if temp_c < 0.0:
        return (0,) + _UNDER_RANGE[1:]

    for i, zone in enumerate(_ZONES):
        if temp_c <= zone[0]:
            return (i + 1, zone[1], zone[2], zone[3], zone[4])

    return (0,) + _OVER_RANGE[1:]


def zone_changed(prev, curr):
    """Returns True if the zone number has changed between two get_zone results."""
    return prev[0] != curr[0]
