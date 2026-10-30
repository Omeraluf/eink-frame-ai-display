// Board settings — safe to commit (WiFi credentials live in secrets.h)
#pragma once

// Raw 1-bit frame published by the server (tools/convert.py for now)
#define IMAGE_URL "http://192.168.0.109:8000/frame.bin" // Mac's LAN IP while testing

#define FRAME_WIDTH  800
#define FRAME_HEIGHT 480
#define FRAME_BYTES  (FRAME_WIDTH * FRAME_HEIGHT / 8) // 48000

// Daily refresh time, local time
#define WAKE_HOUR   10
#define WAKE_MINUTE 0
// POSIX TZ for Asia/Jerusalem (DST from the Friday before the last Sunday of March to the last Sunday of October)
#define TIMEZONE    "IST-2IDT,M3.4.4/26,M10.5.0"
#define NTP_SERVER  "pool.ntp.org"

// A timer wake this close before WAKE time counts as today's refresh (absorbs RTC drift)
#define EARLY_WAKE_MARGIN_S (2 * 3600)
// After reset/power-on, stay awake this long so the board can be flashed over USB
#define FLASH_WINDOW_MS 60000

// Buttons on the EE04 board, active-low
#define BUTTON_1_PIN 2 // refresh now
#define BUTTON_2_PIN 3 // reserved: status screen (step 7)
#define BUTTON_3_PIN 5 // reserved

#define WIFI_TIMEOUT_MS 20000
#define HTTP_TIMEOUT_MS 15000
#define NTP_TIMEOUT_MS  10000
