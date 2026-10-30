// Board settings — safe to commit (WiFi credentials live in secrets.h)
#pragma once

// Raw 1-bit frame published by the server (tools/convert.py for now)
#define IMAGE_URL "http://192.168.0.109:8000/frame.bin" // Mac's LAN IP while testing

#define FRAME_WIDTH  800
#define FRAME_HEIGHT 480
#define FRAME_BYTES  (FRAME_WIDTH * FRAME_HEIGHT / 8) // 48000

#define WIFI_TIMEOUT_MS 20000
#define HTTP_TIMEOUT_MS 15000
