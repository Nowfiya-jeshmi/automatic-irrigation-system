"""
main.py — Smart Irrigation Node firmware (MicroPython, ESP8266/NodeMCU)
Fully self-contained single file: credentials, config, and control logic
all in one place. Nothing else needs to be uploaded to the device.

*** SECURITY WARNING ***
Your WiFi password and Blynk token are stored in plain text below. If this
repo is public on GitHub, anyone can read them. Either:
  (a) keep this repo PRIVATE, or
  (b) before pushing, replace the real values below with placeholders again
      (or better: go back to the secrets.py-based version so credentials
      never touch git history at all).
If you accidentally push real credentials to a public repo, treat them as
compromised — change your WiFi password and regenerate the Blynk token.

Real-time / production notes:
  * Watering is a NON-BLOCKING state machine, not a blocking time.sleep().
    A blocking sleep longer than the watchdog timeout would reset the board
    mid-cycle every time it waters — this avoids that entirely.
  * Rain is re-checked every tick while watering, so the pump shuts off
    immediately if it starts raining mid-cycle.
  * Config writes are atomic (temp file + rename) so a power loss can't
    corrupt the on-flash config.
  * Blynk query values are URL-encoded.
  * Log file is truncated once it passes MAX_LOG_BYTES so it can't fill flash.
  * Soil readings are averaged over several samples to cut down on noise.
  * A minimum interval is enforced between watering cycles.
"""

import network
import time
import machine
import urequests
import ujson
import gc
import os
from machine import Pin, ADC, WDT

# ===============================================================
# ==================== CREDENTIALS (EDIT ME) =====================
# ===============================================================

WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
BLYNK_AUTH_TOKEN = "YOUR_BLYNK_AUTH_TOKEN"

# ===============================================================
# ========================== CONFIG ==============================
# ===============================================================

FIRMWARE_VERSION = "4.1.0"
DEVICE_NAME = "SMART_IRRIGATION_NODE_01"
DEBUG_MODE = True

CONFIG_FILE = "irrigation_config.json"
LOG_FILE = "irrigation_logs.txt"
MAX_LOG_BYTES = 40_000          # rotate/truncate log before flash fills up

# ---- Hardware pins (ESP8266 / NodeMCU numbering) ----
SOIL_SENSOR_ADC = 0             # A0 (ESP8266 has exactly one ADC channel)
RAIN_SENSOR_PIN = 14            # D5
PUMP_RELAY_PIN = 12             # D6
STATUS_LED_PIN = 2              # Built-in LED (active-low on most boards)

# ---- Soil moisture thresholds (raw ADC 0-1023, sensor-dependent — calibrate!) ----
SOIL_DRY_THRESHOLD = 600
SOIL_WET_THRESHOLD = 350
RAIN_DETECTED_LEVEL = 0         # digital rain sensor: LOW usually means "wet"
SOIL_SAMPLE_COUNT = 5           # averaged readings, reduces sensor noise
SOIL_SAMPLE_DELAY_MS = 20

# ---- Timing (seconds unless noted) ----
WATERING_DURATION = 10
MIN_INTERVAL_BETWEEN_WATERING = 300     # don't re-trigger for 5 min after a cycle
STATUS_INTERVAL = 15
WIFI_CHECK_INTERVAL = 20
HEARTBEAT_INTERVAL = 30
MEMORY_CHECK_INTERVAL = 25
MAIN_LOOP_TICK = 1               # must stay well under WDT_TIMEOUT_MS
WDT_TIMEOUT_MS = 8000

# ---- Blynk virtual pins ----
VPIN_SOIL = "V1"
VPIN_WATER_COUNT = "V2"
VPIN_RSSI = "V3"
VPIN_HEARTBEAT = "V6"

# ===============================================================
# ========================== BOOT HOUSEKEEPING ===================
# ===============================================================
try:
    import esp
    esp.osdebug(None)   # quiet the low-level debug UART spam
except ImportError:
    pass
gc.collect()

# ===============================================================
# ========================== LOGGER ==============================
# ===============================================================

class Logger:
    def __init__(self):
        self._rotate_if_needed()

    def _rotate_if_needed(self):
        try:
            size = os.stat(LOG_FILE)[6]
            if size > MAX_LOG_BYTES:
                with open(LOG_FILE, "r") as f:
                    data = f.read()
                with open(LOG_FILE, "w") as f:
                    f.write(data[len(data) // 2:])
        except OSError:
            pass  # file doesn't exist yet

    def log(self, level, message):
        entry = "[{}][{}] {}".format(time.time(), level, message)
        if DEBUG_MODE:
            print(entry)
        try:
            self._rotate_if_needed()
            with open(LOG_FILE, "a") as f:
                f.write(entry + "\n")
        except OSError:
            pass


logger = Logger()

# ===============================================================
# ===================== CONFIG MANAGER ==========================
# ===============================================================

class ConfigManager:
    """Persists small bits of runtime state (counts, override flag) to flash.
    Writes are atomic: write to a temp file then rename, so a mid-write power
    loss never leaves a half-written / corrupt config file behind.
    """

    def __init__(self):
        self.data = {
            "system_enabled": True,
            "manual_override": False,
            "watering_count": 0,
            "total_water_time": 0,
        }

    def load(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = ujson.load(f)
            self.data.update(loaded)
            logger.log("INFO", "Config loaded")
        except (OSError, ValueError):
            logger.log("WARN", "No valid config found, using defaults")
            self.save()

    def save(self):
        tmp_file = CONFIG_FILE + ".tmp"
        try:
            with open(tmp_file, "w") as f:
                ujson.dump(self.data, f)
            os.rename(tmp_file, CONFIG_FILE)
        except OSError as e:
            logger.log("ERROR", "Config save failed: {}".format(e))


config = ConfigManager()
config.load()

# ===============================================================
# ======================== WIFI MANAGER =========================
# ===============================================================

class WiFiManager:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self._backoff = 1

    def connect(self):
        if self.wlan.isconnected():
            return
        logger.log("INFO", "Connecting WiFi...")
        self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        timeout = 0
        while not self.wlan.isconnected() and timeout < 20:
            time.sleep(1)
            timeout += 1

        if self.wlan.isconnected():
            logger.log("INFO", "WiFi connected, IP={}".format(self.wlan.ifconfig()[0]))
            self._backoff = 1
        else:
            logger.log("ERROR", "WiFi connect failed, backing off {}s".format(self._backoff))
            time.sleep(self._backoff)
            self._backoff = min(self._backoff * 2, 60)  # exponential backoff, capped

    def check(self):
        if not self.wlan.isconnected():
            logger.log("WARN", "WiFi lost. Reconnecting...")
            self.connect()

    def rssi(self):
        try:
            return self.wlan.status("rssi")
        except Exception:
            return 0


wifi = WiFiManager()
wifi.connect()

# ===============================================================
# ======================== BLYNK CLIENT =========================
# ===============================================================

def url_encode(s):
    """Minimal percent-encoder — MicroPython has no urllib.parse."""
    safe = "-_.~"
    out = []
    for ch in str(s):
        if ch.isalpha() or ch.isdigit() or ch in safe:
            out.append(ch)
        else:
            out.append("%{:02X}".format(ord(ch)))
    return "".join(out)


class BlynkClient:
    BASE = "https://blynk.cloud/external/api"

    def update(self, pin, value):
        url = "{}/update?token={}&{}={}".format(
            self.BASE, BLYNK_AUTH_TOKEN, pin, url_encode(value)
        )
        self._get(url, "update {}".format(pin))

    def log_event(self, event, message):
        url = "{}/logEvent?token={}&event={}&description={}".format(
            self.BASE, BLYNK_AUTH_TOKEN, url_encode(event), url_encode(message)
        )
        self._get(url, "logEvent {}".format(event))

    def _get(self, url, what):
        if not wifi.wlan.isconnected():
            return
        r = None
        try:
            r = urequests.get(url)
        except Exception as e:
            logger.log("ERROR", "Blynk {} failed: {}".format(what, e))
        finally:
            if r is not None:
                r.close()


blynk = BlynkClient()

# ===============================================================
# ======================== HARDWARE LAYER =======================
# ===============================================================

class Hardware:
    def __init__(self):
        self.soil_sensor = ADC(SOIL_SENSOR_ADC)
        self.rain_sensor = Pin(RAIN_SENSOR_PIN, Pin.IN)
        self.pump = Pin(PUMP_RELAY_PIN, Pin.OUT)
        self.status_led = Pin(STATUS_LED_PIN, Pin.OUT)
        self.pump.off()

    def read_soil_avg(self):
        """Average several samples to smooth out ADC/sensor noise."""
        total = 0
        for _ in range(SOIL_SAMPLE_COUNT):
            total += self.soil_sensor.read()
            time.sleep_ms(SOIL_SAMPLE_DELAY_MS)
        return total // SOIL_SAMPLE_COUNT

    def is_raining(self):
        return self.rain_sensor.value() == RAIN_DETECTED_LEVEL

    def pump_on(self):
        self.pump.on()
        self.status_led.on()

    def pump_off(self):
        self.pump.off()
        self.status_led.off()


hardware = Hardware()

# ===============================================================
# ===================== IRRIGATION ENGINE =======================
# ===============================================================

class IrrigationEngine:
    """State machine, not a blocking function — this is the core fix.
    Watering runs across multiple main-loop ticks so the watchdog keeps
    getting fed and rain can abort a cycle in progress.
    """

    def __init__(self):
        self.watering = False
        self.watering_start = 0
        self.last_watering_end = -MIN_INTERVAL_BETWEEN_WATERING

    def evaluate(self):
        if self.watering:
            self._tick_watering()
            return

        if not config.data["system_enabled"]:
            return

        now = time.time()
        if now - self.last_watering_end < MIN_INTERVAL_BETWEEN_WATERING:
            return

        if config.data["manual_override"]:
            self._start("Manual override")
            return

        soil = hardware.read_soil_avg()
        raining = hardware.is_raining()
        logger.log("INFO", "Soil={} Rain={}".format(soil, raining))

        if raining:
            return

        if soil > SOIL_DRY_THRESHOLD:
            self._start("Soil dry (reading={})".format(soil))

    def _start(self, reason):
        logger.log("WARN", "Watering started - {}".format(reason))
        blynk.log_event("watering_event", reason)
        hardware.pump_on()
        self.watering = True
        self.watering_start = time.time()

    def _tick_watering(self):
        if hardware.is_raining():
            logger.log("INFO", "Rain detected mid-cycle, aborting watering")
            self._stop()
            return
        if time.time() - self.watering_start >= WATERING_DURATION:
            self._stop()

    def _stop(self):
        elapsed = time.time() - self.watering_start
        hardware.pump_off()
        self.watering = False
        self.last_watering_end = time.time()
        config.data["watering_count"] += 1
        config.data["total_water_time"] += elapsed
        config.save()
        logger.log("INFO", "Watering stopped after {}s".format(elapsed))


engine = IrrigationEngine()

# ===============================================================
# ===================== HEALTH MONITOR ==========================
# ===============================================================

class HealthMonitor:
    def memory_check(self):
        gc.collect()
        free = gc.mem_free()
        logger.log("DEBUG", "Free memory: {}".format(free))
        if free < 4000:
            logger.log("ERROR", "Low memory - resetting")
            machine.reset()

    def diagnostics(self):
        logger.log("INFO", "Firmware: {}".format(FIRMWARE_VERSION))
        logger.log("INFO", "Device: {}".format(DEVICE_NAME))
        logger.log("INFO", "RSSI: {}".format(wifi.rssi()))
        logger.log("INFO", "Water cycles: {}".format(config.data["watering_count"]))


health = HealthMonitor()

wdt = WDT(timeout=WDT_TIMEOUT_MS)

# ===============================================================
# ========================= SCHEDULER ===========================
# ===============================================================

class Scheduler:
    def __init__(self):
        self.last_status = 0
        self.last_wifi = 0
        self.last_memory = 0
        self.last_heartbeat = 0

    def run(self):
        now = time.time()

        if now - self.last_status > STATUS_INTERVAL:
            self.last_status = now
            self.send_status()

        if now - self.last_wifi > WIFI_CHECK_INTERVAL:
            self.last_wifi = now
            wifi.check()

        if now - self.last_memory > MEMORY_CHECK_INTERVAL:
            self.last_memory = now
            health.memory_check()

        if now - self.last_heartbeat > HEARTBEAT_INTERVAL:
            self.last_heartbeat = now
            blynk.update(VPIN_HEARTBEAT, "ONLINE")

    def send_status(self):
        blynk.update(VPIN_SOIL, hardware.soil_sensor.read())
        blynk.update(VPIN_WATER_COUNT, config.data["watering_count"])
        blynk.update(VPIN_RSSI, wifi.rssi())
        logger.log("INFO", "Status updated")


scheduler = Scheduler()

# ===============================================================
# ========================== MAIN LOOP ==========================
# ===============================================================

logger.log("INFO", "Smart Irrigation System booted")
health.diagnostics()

while True:
    try:
        engine.evaluate()
        scheduler.run()
        wdt.feed()
        time.sleep(MAIN_LOOP_TICK)

    except Exception as e:
        logger.log("ERROR", "Runtime error: {}".format(e))
        # Fail safe: never leave the pump running if something went wrong.
        try:
            hardware.pump_off()
        except Exception:
            pass
        wdt.feed()
        time.sleep(2)
