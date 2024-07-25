 
import time
 
 
class DataLogger:
    """
    Circular buffer for sensor readings.
    Once full, new entries overwrite the oldest.
    """
 
    def __init__(self, max_entries=300):
        """
        Args:
            max_entries: Maximum number of readings to store (default 300 ~= 2.5 min at 500ms poll)
        """
        self.max_entries = max_entries
        self._entries = []
        self._write_index = 0
        self._is_full = False
 
    def log(self, temp_c, smoke_raw, smoke_level, zone, servo_angle, fan_on, buzzer_on):
        """
        Log a sensor reading.
 
        Args:
            temp_c:       Temperature in Celsius (float)
            smoke_raw:    Raw ADC value 0-4095 (int)
            smoke_level:  String "normal", "high", or "critical"
            zone:         Zone number 1-4 or 0 (int)
            servo_angle:  Servo position 0-90 (int)
            fan_on:       Boolean
            buzzer_on:    Boolean
        """
        entry = {
            "ts": time.time(),
            "temp": temp_c,
            "smoke_raw": smoke_raw,
            "smoke_level": smoke_level,
            "zone": zone,
            "servo": servo_angle,
            "fan": fan_on,
            "buzzer": buzzer_on,
        }
 
        if len(self._entries) < self.max_entries:
            self._entries.append(entry)
        else:
            self._entries[self._write_index] = entry
            self._write_index = (self._write_index + 1) % self.max_entries
            self._is_full = True
 
    def get_latest(self):
        """Return the most recent entry, or None if no entries yet."""
        if not self._entries:
            return None
        return self._entries[-1]
 
    def get_last_n(self, n):
        """Return the last n entries as a list."""
        if not self._entries:
            return []
        if n >= len(self._entries):
            return self._entries[:]
        return self._entries[-n:]
 
    def get_all(self):
        """Return all entries in chronological order."""
        return self._entries[:]
 
    def clear(self):
        """Clear all entries."""
        self._entries = []
        self._write_index = 0
        self._is_full = False
 
    def count(self):
        """Return the number of entries stored."""
        return len(self._entries)
 
