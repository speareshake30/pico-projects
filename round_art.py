"""
SB Components 1.28" Round LCD HAT — Colorful demo
Pins: SPI1 SCK=10 MOSI=11 MISO=12 | CS=9 DC=8 RST=12 BL=13
"""
from machine import Pin, SPI, PWM
import time
import framebuf
import math
import random

CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(0)
MISO = Pin(12, Pin.IN)  # Share RST pin, not used for SPI reads

# SPI1 — MISO MUST be on a pin other than GP8 (DC conflict)
spi = SPI(1, baudrate=40_000_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=MISO)

W, H = 240, 240

def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def cmd(b, *data):
    DC(0); CS(0); spi.write(bytes([b])); CS(1)
    if data: DC(1); CS(0); spi.write(bytes(data)); CS(1)

# ── Init GC9A01 ──
RST(0); time.sleep_ms(20); RST(1); time.sleep_ms(150)

cmd(0x01); time.sleep_ms(150)
cmd(0x11); time.sleep_ms(120)
cmd(0x3A, 0x55)  # 16-bit RGB565
cmd(0x36, 0x00)  # MADCTL

# Gamma/voltage
cmd(0xF0, 0x45,0x09,0x08,0x08,0x26,0x2A)
cmd(0xF1, 0x43,0x70,0x72,0x36,0x37,0x6F)
cmd(0xF2, 0x45,0x09,0x08,0x08,0x26,0x2A)
cmd(0xF3, 0x43,0x70,0x72,0x36,0x37,0x6F)
cmd(0x21)  # INVON
cmd(0x29); time.sleep_ms(100)

BL.duty_u16(65535)
print('Init done')

# ── Framebuffer ──
buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)

# ── Colorful concentric rainbow rings ──
cx, cy = 120, 120
for radius in range(120, 2, -2):
    hue = (120 - radius) / 120.0
    r = int(127 + 127 * math.sin(hue * math.pi * 2))
    g = int(127 + 127 * math.sin(hue * math.pi * 2 + 2.094))
    b = int(127 + 127 * math.sin(hue * math.pi * 2 + 4.189))
    fb.ellipse(cx, cy, radius, radius, rgb565(r, g, b), True)

# ── Stars ──
for _ in range(60):
    angle = random.uniform(0, math.pi * 2)
    dist = random.uniform(15, 115)
    x = int(cx + dist * math.cos(angle))
    y = int(cy + dist * math.sin(angle))
    if 0 <= x < W and 0 <= y < H:
        brightness = random.randint(150, 255)
        fb.pixel(x, y, rgb565(brightness, brightness, brightness))

# ── Planet / central orb ──
for r in range(30, 0, -1):
    t = r / 30.0
    cr = int(40 + (1-t) * 200)
    cg = int(100 + t * 100)
    cb = int(200 + t * 55)
    fb.ellipse(cx, cy, r, r, rgb565(cr, cg, cb), True)

# ── Text labels ──
fb.text('RAWDOG1', 45, 30, rgb565(255, 255, 255))
fb.text('ROUND', 60, 190, rgb565(255, 220, 100))
fb.text('LCD', 80, 205, rgb565(255, 220, 100))

# ── Push to display ──
def set_window(x, y, w, h):
    cmd(0x2A, x>>8, x&0xFF, (x+w-1)>>8, (x+w-1)&0xFF)
    cmd(0x2B, y>>8, y&0xFF, (y+h-1)>>8, (y+h-1)&0xFF)
    cmd(0x2C)

set_window(0, 0, W, H)
CS(0); DC(1); spi.write(buf); CS(1)
print('Artwork pushed!')