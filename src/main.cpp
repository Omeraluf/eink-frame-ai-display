#include <Arduino.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h> // Seeed_GFX keeps the TFT_eSPI header name
#include <WiFi.h>

#include "config.h"
#include "secrets.h"

EPaper epaper;
static uint8_t frame[FRAME_BYTES]; // 1 bit per pixel, MSB first, bit set = black

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

void setup() {
  Serial.begin(115200);
  delay(1000); // give USB serial a moment so early logs aren't lost

  bool ok = connectWiFi() && downloadFrame();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);

  if (!ok) {
    Serial.println("Keeping the previous image");
    return; // e-paper holds its last picture without power
  }
  epaper.begin();
  epaper.fillScreen(TFT_WHITE);
  epaper.drawBitmap(0, 0, frame, FRAME_WIDTH, FRAME_HEIGHT, TFT_BLACK);
  epaper.update(); // e-paper only refreshes on update()
  Serial.println("Display updated");
}

void loop() {}
