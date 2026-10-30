#include <Arduino.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h> // Seeed_GFX keeps the TFT_eSPI header name
#include <WiFi.h>
#include <driver/rtc_io.h>
#include <esp_sleep.h>
#include <time.h>

#include "config.h"
#include "secrets.h"

EPaper epaper;
static uint8_t frame[FRAME_BYTES]; // 1 bit per pixel, MSB first, bit set = black

static const gpio_num_t BUTTONS[] = {(gpio_num_t)BUTTON_1_PIN, (gpio_num_t)BUTTON_2_PIN,
                                     (gpio_num_t)BUTTON_3_PIN};

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
  Serial.printf(" ok, IP %s\n", WiFi.localIP().toString().c_str());
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
    Serial.printf("HTTP: GET %s failed: %d\n", IMAGE_URL, code);
    http.end();
    return false;
  }
  int size = http.getSize();
  if (size != FRAME_BYTES) {
    Serial.printf("HTTP: expected %d bytes, server says %d\n", FRAME_BYTES, size);
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
    Serial.printf("HTTP: only received %u of %d bytes\n", got, FRAME_BYTES);
    return false;
  }
  Serial.println("HTTP: frame downloaded");
  return true;
}

void showFrame() {
  epaper.begin();
  epaper.fillScreen(TFT_WHITE);
  epaper.drawBitmap(0, 0, frame, FRAME_WIDTH, FRAME_HEIGHT, TFT_BLACK);
  epaper.update(); // e-paper only refreshes on update()
  Serial.println("Display updated");
}

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

void setup() {
  Serial.begin(115200);
  delay(1000); // give USB serial a moment so early logs aren't lost

  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  bool timerWake = cause == ESP_SLEEP_WAKEUP_TIMER;
  if (cause == ESP_SLEEP_WAKEUP_EXT1) {
    uint64_t pins = esp_sleep_get_ext1_wakeup_status();
    Serial.printf("Woke: button (GPIO mask 0x%llx)\n", pins);
  } else {
    Serial.println(timerWake ? "Woke: timer" : "Woke: reset/power-on");
  }

  bool ok = false;
  if (connectWiFi()) {
    syncTime();
    ok = downloadFrame();
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  if (ok) {
    showFrame();
  } else {
    Serial.println("Keeping the previous image"); // e-paper holds its last picture without power
  }

  // Deep sleep turns off USB, so after a manual reset leave time to flash new firmware
  if (cause == ESP_SLEEP_WAKEUP_UNDEFINED) {
    Serial.printf("Flash window: staying awake %d s\n", FLASH_WINDOW_MS / 1000);
    delay(FLASH_WINDOW_MS);
  }
  deepSleep(secondsUntilNextWake(timerWake));
}

void loop() {}
