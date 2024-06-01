"""
main.py
Combustion controller - with graceful hardware failure handling.

If a sensor or output is not wired, the program logs the error and continues
without it. This lets you test with just the thermocouple, or just the servo,
or any combination.

Hardware is initialized in try/except blocks. Missing hardware = skip it.
"""

import time
import _thread
from temp_sensor    import MAX6675
from servo_control  import Servo
from fan_control    import Fan
from lcd_display    import LCD
from zone_logic     import get_zone, zone_changed
from smoke_sensor   import SmokeSensor
from smoke_override import SmokeOverride
from data_logger    import DataLogger
from web_server     import WebServer

# ---------------------------------------------------------------------------
# Pin configuration
# ---------------------------------------------------------------------------

THERMO_SCK   = 18
THERMO_CS    = 5
THERMO_SO    = 19
THERMO_MOSI  = 2

SERVO_PIN    = 13

FAN_PIN          = 14
RELAY_ACTIVE_LOW = False

SMOKE_PIN    = 34
BUZZER_PIN   = 27

LCD_SDA      = 21
LCD_SCL      = 22
LCD_ADDR     = 0x27

POLL_MS      = 500
FAULT_MAX    = 3

WIFI_SSID     = "your-ssid-here"
WIFI_PASSWORD = "your-password-here"

# ---------------------------------------------------------------------------
# Graceful hardware initialization
# ---------------------------------------------------------------------------

def init_hardware():
    """
    Initialize all hardware. If something fails, log it and continue.
    Returns a dict of what succeeded and what failed.
    """
    status = {
        "lcd": None,
        "temp_sensor": None,
        "servo": None,
        "fan": None,
        "smoke_sensor": None,
        "override": None,
        "logger": None,
        "web_server": None,
    }

    # LCD
    print("[Init] Initializing LCD...")
    try:
        status["lcd"] = LCD(sda=LCD_SDA, scl=LCD_SCL, i2c_address=LCD_ADDR)
        status["lcd"].clear()
        status["lcd"].write(0, "Combustion Ctrl")
        status["lcd"].write(1, "Starting...     ")
        print("[Init] LCD OK")
    except Exception as e:
        print("[Init] LCD FAILED: {}".format(e))
        status["lcd"] = None

    # Thermocouple (MAX6675)
    print("[Init] Initializing MAX6675...")
    try:
        status["temp_sensor"] = MAX6675(sck=THERMO_SCK, cs=THERMO_CS,
                                        so=THERMO_SO, dummy_mosi=THERMO_MOSI)
        status["temp_sensor"].read_celsius()  # Test it
        print("[Init] MAX6675 OK")
    except Exception as e:
        print("[Init] MAX6675 FAILED: {}".format(e))
        status["temp_sensor"] = None

    # Servo
    print("[Init] Initializing servo...")
    try:
        status["servo"] = Servo(pin=SERVO_PIN)
        print("[Init] Servo OK")
    except Exception as e:
        print("[Init] Servo FAILED: {}".format(e))
        status["servo"] = None

    # Fan
    print("[Init] Initializing fan...")
    try:
        status["fan"] = Fan(pin=FAN_PIN, active_low=RELAY_ACTIVE_LOW)
        print("[Init] Fan OK")
    except Exception as e:
        print("[Init] Fan FAILED: {}".format(e))
        status["fan"] = None

    # Smoke sensor
    print("[Init] Initializing smoke sensor...")
    try:
        status["smoke_sensor"] = SmokeSensor(pin=SMOKE_PIN)
        status["smoke_sensor"].read_raw()  # Test it
        print("[Init] Smoke sensor OK")
    except Exception as e:
        print("[Init] Smoke sensor FAILED: {}".format(e))
        status["smoke_sensor"] = None

    # Smoke override / buzzer
    print("[Init] Initializing buzzer...")
    try:
        status["override"] = SmokeOverride(buzzer_pin=BUZZER_PIN)
        print("[Init] Buzzer OK")
    except Exception as e:
        print("[Init] Buzzer FAILED: {}".format(e))
        status["override"] = None

    # Data logger (should always work)
    print("[Init] Initializing data logger...")
    try:
        status["logger"] = DataLogger(max_entries=400)
        print("[Init] Data logger OK")
    except Exception as e:
        print("[Init] Data logger FAILED: {}".format(e))
        status["logger"] = None

    # Web server
    print("[Init] Initializing web server...")
    try:
        status["web_server"] = WebServer(status["logger"], 
                                         ssid=WIFI_SSID, 
                                         password=WIFI_PASSWORD)
        print("[Init] Web server created (will connect to WiFi)")
    except Exception as e:
        print("[Init] Web server FAILED: {}".format(e))
        status["web_server"] = None

    # Summary
    print("\n[Init] ===== Hardware Status =====")
    for name, obj in status.items():
        state = "OK" if obj is not None else "MISSING"
        print("[Init] {}: {}".format(name, state))
    print("[Init] ==============================\n")

    return status


def lcd_write(lcd, row, text):
    """Safely write to LCD if it exists."""
    if lcd:
        try:
            lcd.write(row, text)
        except:
            pass


def run_web_server_thread(web_server):
    """Runs in a background thread."""
    try:
        web_server.start()
    except Exception as e:
        print("[WebServer] Error: {}".format(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    # Initialize hardware (gracefully skip missing pieces)
    hw = init_hardware()

    lcd = hw["lcd"]
    sensor = hw["temp_sensor"]
    servo = hw["servo"]
    fan = hw["fan"]
    smoke = hw["smoke_sensor"]
    override = hw["override"]
    logger = hw["logger"]
    web_server = hw["web_server"]

    # Check if we have the bare minimum (temperature sensor)
    if not sensor:
        print("[Main] ERROR: No temperature sensor detected!")
        print("[Main] Exiting.")
        while True:
            time.sleep(1)

    lcd_write(lcd, 0, "Hardware check  ")
    time.sleep_ms(800)

    # Start web server in background if it exists
    if web_server:
        lcd_write(lcd, 0, "Starting WiFi...")
        lcd_write(lcd, 1, "                ")
        _thread.start_new_thread(run_web_server_thread, (web_server,))
        time.sleep(3)
        lcd = None  # Clear LCD reference so we don't spam it during control loop

    if lcd:
        lcd.clear()

    # State tracking
    prev_zone        = None
    prev_final_angle = -1
    fault_count      = 0

    print("[Main] Starting control loop...")

    # Main loop
    while True:
        t0 = time.ticks_ms()

        # 1. Read temperature (required)
        try:
            temp_c = sensor.read_celsius()
            fault_count = 0
        except RuntimeError:
            fault_count += 1
            print("[Main] Thermocouple fault #{}/{}".format(fault_count, FAULT_MAX))
            if fault_count >= FAULT_MAX:
                print("[Main] Too many faults. Entering safe state.")
                if servo:
                    servo.set_angle(0, wait=False)
                if fan:
                    fan.off()
                if override:
                    override.silence()
                while True:
                    time.sleep(1)
            time.sleep_ms(POLL_MS)
            continue

        # 2. Get zone (based on temp)
        zone = get_zone(temp_c)

        # 3. Apply smoke override (if sensor exists)
        if smoke and override:
            final_angle, buzzer_on = override.apply(zone[1], smoke)
            smoke_raw = smoke.read_raw()
            smoke_level = smoke.classify()
        else:
            final_angle = zone[1]
            buzzer_on = False
            smoke_raw = 0
            smoke_level = "unknown"

        # 4. Log to data logger (if it exists)
        if logger:
            logger.log(
                temp_c=temp_c,
                smoke_raw=smoke_raw,
                smoke_level=smoke_level,
                zone=zone[0],
                servo_angle=final_angle,
                fan_on=fan.is_on if fan else False,
                buzzer_on=buzzer_on,
            )

        # 5. Drive servo (if it exists)
        if servo and final_angle != prev_final_angle:
            servo.set_angle(final_angle, wait=True)
            prev_final_angle = final_angle

        # 6. Drive fan (if it exists and zone changed)
        if fan and (prev_zone is None or zone_changed(prev_zone, zone)):
            fan.set(zone[2])
            prev_zone = zone

        # 7. Update LCD (if it exists)
        if lcd:
            fan_str = "Fan:ON " if (fan and fan.is_on) else "Fan:OFF"
            lcd.write(0, "T:{:5.1f}C {}".format(temp_c, fan_str))
            tick = (time.ticks_ms() // 2000) % 2
            if tick == 0:
                lcd.write(1, zone[4])
            else:
                if override:
                    lcd.write(1, override.get_smoke_label(smoke))
                else:
                    lcd.write(1, "{:d}".format(int(temp_c)))

        # 8. Print to console for debugging
        print("T:{:6.1f}C Z:{} S:{}  Smk:{}".format(
            temp_c, zone[0], final_angle, smoke_level if smoke else "N/A"))

        # 9. Sleep for remainder of poll interval
        elapsed = time.ticks_diff(time.ticks_ms(), t0)
        sleep_ms = max(0, POLL_MS - elapsed)
        time.sleep_ms(sleep_ms)


main()
