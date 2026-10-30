#include <Arduino.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <TFT_eSPI.h> // Seeed_GFX keeps the TFT_eSPI header name
#include <WiFi.h>
#include <driver/rtc_io.h>
#include <esp_sleep.h>
#include <time.h>

#include "config.h"
#include "secrets.h"

EPaper epaper;
static uint8_t frame[FRAME_BYTES]; // 1 bit per pixel, MSB first, bit set = black
static const char *FRAME_FILE = "/frame.bin"; // last good frame, redrawn with icons on failure

static const gpio_num_t BUTTONS[] = {(gpio_num_t)BUTTON_1_PIN, (gpio_num_t)BUTTON_2_PIN,
                                     (gpio_num_t)BUTTON_3_PIN};

// Survives deep sleep (not power loss): shown on the status screen
RTC_DATA_ATTR time_t lastSuccess = 0;
RTC_DATA_ATTR int8_t lastRssi = 0;
RTC_DATA_ATTR char lastResult[48] = "no refresh yet";

void setResult(const char *fmt, ...) {
  va_list args;
  va_start(args, fmt);
  vsnprintf(lastResult, sizeof(lastResult), fmt, args);
  va_end(args);
  Serial.printf("Result: %s\n", lastResult);
}

// ---------- Network ----------

bool connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("WiFi: connecting to %s", WIFI_SSID);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_TIMEOUT_MS) {
      Serial.println(" timed out");
      return false;
    }
    delay(250);
    Serial.print(".");
  }
  lastRssi = WiFi.RSSI();
  Serial.printf(" ok, IP %s, signal %d dBm\n", WiFi.localIP().toString().c_str(), lastRssi);
  return true;
}

// The RTC keeps counting through deep sleep, so an earlier sync stays roughly valid
bool clockIsSet() { return time(nullptr) > 1700000000; } // after Nov 2023

bool syncTime() {
  configTzTime(TIMEZONE, NTP_SERVER);
  struct tm now;
  if (!getLocalTime(&now, NTP_TIMEOUT_MS)) {
    Serial.println("NTP: sync failed");
    return false;
  }
  Serial.printf("NTP: %04d-%02d-%02d %02d:%02d:%02d\n", now.tm_year + 1900, now.tm_mon + 1,
                now.tm_mday, now.tm_hour, now.tm_min, now.tm_sec);
  return true;
}

// Downloads exactly FRAME_BYTES into `frame`; anything else counts as a failure
bool downloadFrame() {
  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(IMAGE_URL);
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    setResult("server error %d", code);
    http.end();
    return false;
  }
  int size = http.getSize();
  if (size != FRAME_BYTES) {
    setResult("bad size %d bytes", size);
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  size_t got = 0;
  unsigned long start = millis();
  while (got < FRAME_BYTES && millis() - start < HTTP_TIMEOUT_MS) {
    size_t n = stream->readBytes(frame + got, FRAME_BYTES - got);
    if (n == 0 && !http.connected()) break;
    got += n;
  }
  http.end();
  if (got != FRAME_BYTES) {
    setResult("download cut at %u bytes", got);
    return false;
  }
  Serial.println("HTTP: frame downloaded");
  return true;
}

// ---------- Flash ----------

bool saveFrame() {
  File f = LittleFS.open(FRAME_FILE, "w");
  bool ok = f && f.write(frame, FRAME_BYTES) == FRAME_BYTES;
  f.close();
  Serial.println(ok ? "Flash: frame saved" : "Flash: save failed");
  return ok;
}

bool loadFrame() {
  File f = LittleFS.open(FRAME_FILE, "r");
  bool ok = f && f.read(frame, FRAME_BYTES) == FRAME_BYTES;
  f.close();
  Serial.println(ok ? "Flash: frame loaded" : "Flash: no saved frame");
  return ok;
}

// ---------- Battery ----------

int batteryMillivolts() {
  pinMode(BATTERY_ENABLE_PIN, OUTPUT);
  digitalWrite(BATTERY_ENABLE_PIN, HIGH);
  delay(10); // let the divider settle
  uint32_t sum = 0;
  for (int i = 0; i < 10; i++) {
    sum += analogReadMilliVolts(BATTERY_ADC_PIN);
    delay(2);
  }
  digitalWrite(BATTERY_ENABLE_PIN, LOW); // the divider drains the battery while enabled
  int mv = sum / 10 * BATTERY_DIVIDER;
  Serial.printf("Battery: %d mV\n", mv);
  return mv;
}

bool batteryPresent(int mv) { return mv >= BATTERY_ABSENT_MV; }
bool batteryLow(int mv) { return batteryPresent(mv) && mv < BATTERY_LOW_MV; }

int batteryPercent(int mv) {
  return constrain(map(mv, BATTERY_EMPTY_MV, BATTERY_FULL_MV, 0, 100), 0, 100);
}

// ---------- Drawing ----------

// Icons sit in the portrait top-left corner on a white tile; returns the x after the icon
int drawWarningIcon(int x, int y) {
  epaper.fillRoundRect(x, y, 48, 44, 6, TFT_WHITE);
  epaper.fillTriangle(x + 24, y + 4, x + 4, y + 40, x + 44, y + 40, TFT_BLACK);
  epaper.fillTriangle(x + 24, y + 12, x + 11, y + 36, x + 37, y + 36, TFT_WHITE);
  epaper.fillRect(x + 22, y + 18, 4, 10, TFT_BLACK);
  epaper.fillRect(x + 22, y + 31, 4, 4, TFT_BLACK);
  return x + 52;
}

int drawBatteryIcon(int x, int y, int mv) {
  epaper.fillRoundRect(x, y, 60, 44, 6, TFT_WHITE);
  epaper.drawRect(x + 6, y + 12, 42, 20, TFT_BLACK);
  epaper.drawRect(x + 7, y + 13, 40, 18, TFT_BLACK);
  epaper.fillRect(x + 48, y + 17, 5, 10, TFT_BLACK); // terminal nub
  int level = 36 * batteryPercent(mv) / 100;
  epaper.fillRect(x + 9, y + 15, max(level, 3), 14, TFT_BLACK);
  return x + 64;
}

// Draws `frame` plus any icons and refreshes the panel
void showFrame(bool warning, int batteryMv) {
  epaper.setRotation(0);
  epaper.fillScreen(TFT_WHITE);
  epaper.drawBitmap(0, 0, frame, FRAME_WIDTH, FRAME_HEIGHT, TFT_BLACK);
  epaper.setRotation(PORTRAIT_ROTATION);
  int x = 8;
  if (warning) x = drawWarningIcon(x, 8);
  if (batteryLow(batteryMv)) x = drawBatteryIcon(x, 8, batteryMv);
  epaper.update(); // e-paper only refreshes on update()
  Serial.printf("Display updated%s%s\n", warning ? " (warning)" : "",
                batteryLow(batteryMv) ? " (low battery)" : "");
}

String formatTime(time_t t) {
  if (t == 0) return "never";
  struct tm tm;
  localtime_r(&t, &tm);
  char buf[24];
  strftime(buf, sizeof(buf), "%d.%m  %H:%M", &tm);
  return buf;
}

void showStatus(int batteryMv, time_t nextWake) {
  epaper.setRotation(PORTRAIT_ROTATION);
  epaper.fillScreen(TFT_WHITE);
  epaper.setTextColor(TFT_BLACK, TFT_WHITE);
  epaper.setTextDatum(TL_DATUM);

  epaper.setFreeFont(&FreeSansBold18pt7b);
  epaper.drawString("Status", 24, 30);
  epaper.drawFastHLine(24, 78, 432, TFT_BLACK);

  String battery = !batteryPresent(batteryMv)
                       ? String("not connected")
                       : String(batteryMv / 1000.0, 2) + " V  (~" + batteryPercent(batteryMv) + "%)";
  struct Row { const char *label; String value; } rows[] = {
      {"Last update", formatTime(lastSuccess)},
      {"Last result", lastResult},
      {"Next refresh", formatTime(nextWake)},
      {"Battery", battery},
      {"WiFi", String(WIFI_SSID) + (lastRssi ? "  " + String(lastRssi) + " dBm" : "")},
      {"Server", IMAGE_URL},
      {"Firmware", __DATE__ " " __TIME__},
  };
  int y = 104;
  for (const Row &row : rows) {
    epaper.setFreeFont(&FreeSans9pt7b);
    epaper.drawString(row.label, 24, y);
    epaper.setFreeFont(&FreeSansBold12pt7b);
    epaper.drawString(row.value, 24, y + 22);
    y += 76;
  }
  epaper.setFreeFont(&FreeSans9pt7b);
  epaper.drawString("Back to the picture in 30 s", 24, 760);
  epaper.update();
  Serial.println("Status screen shown");
}

// ---------- Sleep ----------

// Seconds until the next WAKE_HOUR:WAKE_MINUTE. A timer wake that fired up to
// EARLY_WAKE_MARGIN_S early already did today's refresh, so it skips to tomorrow.
uint64_t secondsUntilNextWake(bool timerWake) {
  if (!clockIsSet()) return 24ULL * 3600; // no idea what time it is: try again in a day
  time_t now = time(nullptr);
  struct tm target;
  localtime_r(&now, &target);
  target.tm_hour = WAKE_HOUR;
  target.tm_min = WAKE_MINUTE;
  target.tm_sec = 0;
  time_t next = mktime(&target);
  long minAhead = timerWake ? EARLY_WAKE_MARGIN_S : 60;
  if (next - now < minAhead) {
    target.tm_mday += 1; // mktime normalizes month ends and DST changes
    target.tm_isdst = -1;
    next = mktime(&target);
  }
  return next - now;
}

void deepSleep(uint64_t seconds) {
  uint64_t mask = 0;
  for (gpio_num_t pin : BUTTONS) {
    mask |= 1ULL << pin;
    rtc_gpio_pullup_en(pin); // keep buttons high while asleep; pressing pulls low
    rtc_gpio_pulldown_dis(pin);
  }
  esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
  esp_sleep_enable_ext1_wakeup(mask, ESP_EXT1_WAKEUP_ANY_LOW);
  esp_sleep_enable_timer_wakeup(seconds * 1000000ULL);
  Serial.printf("Sleeping %llu s (%.1f h)\n", seconds, seconds / 3600.0);
  Serial.flush();
  esp_deep_sleep_start();
}

// ---------- Main ----------

// Refresh: download a new frame; on failure redraw the saved one with a warning icon
void refresh(int batteryMv) {
  bool ok = false;
  if (connectWiFi()) {
    syncTime();
    ok = downloadFrame();
  } else {
    setResult("WiFi failed");
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  if (ok) {
    lastSuccess = time(nullptr);
    setResult("ok");
    saveFrame();
    showFrame(false, batteryMv);
  } else if (loadFrame()) {
    showFrame(true, batteryMv);
  } else {
    Serial.println("Keeping the previous image"); // nothing saved yet to add the icon to
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000); // give USB serial a moment so early logs aren't lost
  setenv("TZ", TIMEZONE, 1); // local time for the status screen even without WiFi
  tzset();

  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  bool timerWake = cause == ESP_SLEEP_WAKEUP_TIMER;
  uint64_t pins = cause == ESP_SLEEP_WAKEUP_EXT1 ? esp_sleep_get_ext1_wakeup_status() : 0;
  bool statusButton = pins & (1ULL << BUTTON_2_PIN);
  if (pins) {
    Serial.printf("Woke: button (GPIO mask 0x%llx)\n", pins);
  } else {
    Serial.println(timerWake ? "Woke: timer" : "Woke: reset/power-on");
  }

  if (!LittleFS.begin(true)) Serial.println("Flash: LittleFS unavailable"); // formats on first use
  int batteryMv = batteryMillivolts();
  epaper.begin();

  if (statusButton) {
    showStatus(batteryMv, time(nullptr) + secondsUntilNextWake(false));
    delay(STATUS_SCREEN_MS);
    if (loadFrame()) showFrame(false, batteryMv);
  } else {
    refresh(batteryMv);
  }

  // Deep sleep turns off USB, so after a manual reset leave time to flash new firmware
  if (cause == ESP_SLEEP_WAKEUP_UNDEFINED) {
    Serial.printf("Flash window: staying awake %d s\n", FLASH_WINDOW_MS / 1000);
    delay(FLASH_WINDOW_MS);
  }
  deepSleep(secondsUntilNextWake(timerWake));
}

void loop() {}
