// Board settings — safe to commit (WiFi credentials live in secrets.h)
#pragma once

// Raw 1-bit frame published by the server (server/build_frame.py)
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
#define BUTTON_2_PIN 3 // status screen, then back to the picture
#define BUTTON_3_PIN 5 // refresh now (spare)
#define STATUS_SCREEN_MS 30000

// The frame is composed in portrait; Sprite rotation 1 draws overlays the same way up
#define PORTRAIT_ROTATION 1

// Battery on the EE04 board: ADC on GPIO1 behind a 1:2 divider, measurement enabled by GPIO6 HIGH
#define BATTERY_ADC_PIN     1
#define BATTERY_ENABLE_PIN  6
#define BATTERY_DIVIDER     2.0
#define BATTERY_LOW_MV      3500 // show the battery icon below this
#define BATTERY_ABSENT_MV   2500 // readings below this mean no battery is connected
#define BATTERY_EMPTY_MV    3300 // 0% and 100% for the rough percentage on the status screen
#define BATTERY_FULL_MV     4200

#define WIFI_TIMEOUT_MS 20000
#define HTTP_TIMEOUT_MS 15000
#define NTP_TIMEOUT_MS  10000
