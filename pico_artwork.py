"""
Pimoroni Pico Display 2.0 — ST7789 320x240 IPS LCD
Cosmic artwork: nebula gradient, mandala geometry, starfield, planet
"""
from machine import Pin, SPI, PWM
import framebuf
import time
import math
import random

# ── Pin definitions (Pimoroni Pico Display 2.0) ──
CS  = Pin(17, Pin.OUT, value=1)
DC  = Pin(16, Pin.OUT, value=0)
BL  = PWM(Pin(20))
BL.freq(1000)

# RGB LED (bonus!)
LED_R = PWM(Pin(6));  LED_R.freq(1000)
LED_G = PWM(Pin(7));  LED_G.freq(1000)
LED_B = PWM(Pin(8));  LED_B.freq(1000)

# ── SPI setup ──
spi = SPI(0, baudrate=62_500_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))

# ── Display dimensions ──
W, H = 320, 240

# ── ST7789 driver ──
def cmd(c, *data):
    DC(0); CS(0); spi.write(bytes([c])); CS(1)
    if data:
        DC(1); CS(0); spi.write(bytes(data)); CS(1)

def data(d):
    DC(1); CS(0); spi.write(d if isinstance(d, bytes) else bytes([d])); CS(1)

def init_display():
    BL.duty_u16(0)  # backlight off during init
    cmd(0x01)        # SWRESET
    time.sleep_ms(150)
    cmd(0x11)        # SLPOUT
    time.sleep_ms(50)
    cmd(0x3A, 0x55)  # COLMOD: 16-bit RGB565
    cmd(0x36, 0x70)  # MADCTL: landscape, USB-left
    cmd(0x21)        # INVON (IPS inverted)
    cmd(0x13)        # NORON
    cmd(0x29)        # DISPON
    time.sleep_ms(50)
    BL.duty_u16(65535)  # full brightness

def set_window(x, y, w, h):
    cmd(0x2A, x >> 8, x & 0xFF, (x + w - 1) >> 8, (x + w - 1) & 0xFF)
    cmd(0x2B, y >> 8, y & 0xFF, (y + h - 1) >> 8, (y + h - 1) & 0xFF)
    cmd(0x2C)

def show(fb):
    """Push framebuffer to display"""
    set_window(0, 0, W, H)
    CS(0); DC(1)
    spi.write(fb)
    CS(1)

# ── Color helpers ──
def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def lerp(a, b, t):
    return int(a + (b - a) * t)

def lerp_color(c1, c2, t):
    """Lerp between two (r,g,b) tuples"""
    return (lerp(c1[0], c2[0], t),
            lerp(c1[1], c2[1], t),
            lerp(c1[2], c2[2], t))

# ── Create framebuffer ──
buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)

# ═══════════════════════════════════════════════
#  ARTWORK: "COSMIC DAWN"
# ═══════════════════════════════════════════════

def draw_gradient_sky():
    """Vertical gradient: deep space navy → purple → magenta → warm orange"""
    colors = [
        (0, 0, 20),       # deep navy
        (15, 0, 40),      # dark purple
        (40, 0, 60),      # purple
        (80, 0, 50),      # magenta
        (180, 20, 30),    # red-orange
        (255, 80, 0),     # orange
        (255, 180, 30),   # warm gold
    ]
    for y in range(H):
        t = y / (H - 1)
        # Map t through color stops
        idx = t * (len(colors) - 1)
        i = int(idx)
        frac = idx - i
        if i >= len(colors) - 1:
            c = colors[-1]
        else:
            c = lerp_color(colors[i], colors[i + 1], frac)
        fb.hline(0, y, W, rgb565(*c))

def draw_stars(n=80):
    """Scatter twinkling stars in the darker top portion"""
    for _ in range(n):
        x = random.randint(0, W - 1)
        y = random.randint(0, H // 2)  # top half
        brightness = random.randint(100, 255)
        size = random.randint(1, 2)
        c = rgb565(brightness, brightness, brightness)
        fb.pixel(x, y, c)
        if size > 1 and x < W - 1:
            fb.pixel(x + 1, y, c)

def draw_planet(cx, cy, radius):
    """Draw a colorful planet with ring"""
    # Planet body - gradient from edge to center
    for r in range(radius, 0, -1):
        t = r / radius
        # Teal/cyan to bright cyan gradient
        c = lerp_color((0, 100, 180), (80, 220, 255), 1 - t)
        col = rgb565(*c)
        fb.ellipse(cx, cy, r, r * 8 // 10, col, True)
    
    # Planet ring (ellipse, tilted)
    ring_colors = [
        rgb565(255, 180, 50),
        rgb565(255, 140, 0),
        rgb565(200, 200, 100),
        rgb565(255, 200, 80),
    ]
    for i, ring_r in enumerate(range(radius + 6, radius + 16, 2)):
        fb.ellipse(cx, cy, ring_r, ring_r // 4, ring_colors[i % len(ring_colors)], False)

def draw_mandala(cx, cy, max_r, petals=12):
    """Geometric mandala pattern"""
    for i in range(petals):
        angle = (i / petals) * 2 * math.pi
        # Petal color cycles through the rainbow
        hue_angle = i / petals * 2 * math.pi
        r = int(127 + 127 * math.sin(hue_angle))
        g = int(127 + 127 * math.sin(hue_angle + 2.1))
        b = int(127 + 127 * math.sin(hue_angle + 4.2))
        col = rgb565(r, g, b)
        
        # Draw radiating lines
        for dist in range(5, max_r + 1, 3):
            x = cx + int(dist * math.cos(angle))
            y = cy + int(dist * math.sin(angle))
            if 0 <= x < W and 0 <= y < H:
                fb.pixel(x, y, col)
                # Slight thickness
                if 0 <= x + 1 < W:
                    fb.pixel(x + 1, y, col)
    
    # Concentric rings
    for r in range(10, max_r + 1, 15):
        ring_r = int(127 + 127 * math.sin(r * 0.1))
        ring_g = int(127 + 127 * math.sin(r * 0.1 + 2))
        ring_b = int(127 + 127 * math.sin(r * 0.1 + 4))
        fb.ellipse(cx, cy, r, r, rgb565(ring_r, ring_g, ring_b), False)

def draw_horizon_glow():
    """Soft glowing line at the horizon transition"""
    for y in range(H // 2 - 10, H // 2 + 10):
        alpha = 1 - abs(y - H // 2) / 10
        for x in range(0, W, 2):
            existing = buf[(y * W + x) * 2] | (buf[(y * W + x) * 2 + 1] << 8)
            # Blend white glow
            glow = rgb565(
                int(min(255, 100 * alpha)),
                int(min(255, 220 * alpha)),
                int(min(255, 255 * alpha))
            )
            fb.pixel(x, y, glow)

def draw_text_centered(text, y, color, scale=1):
    """Draw centered text at y position"""
    char_w = 8 * scale
    total_w = len(text) * char_w
    x = (W - total_w) // 2
    fb.text(text, x, y, color)

# ── Build the artwork ──
print("Drawing gradient sky...")
draw_gradient_sky()

print("Drawing stars...")
draw_stars(120)

print("Drawing planet...")
draw_planet(260, 55, 30)

print("Drawing mandala...")
draw_mandala(160, 150, 80, petals=16)

print("Drawing horizon glow...")
draw_horizon_glow()

# ── Text overlay ──
draw_text_centered("RAWDOG1 PICO", H - 35, rgb565(255, 255, 255))
draw_text_centered("DISPLAY 2.0", H - 20, rgb565(200, 200, 255))

# Small stars on top of everything for depth
draw_stars(40)

# ── Light up the RGB LED ──
def set_rgb(r, g, b):
    LED_R.duty_u16(r)
    LED_G.duty_u16(g)
    LED_B.duty_u16(b)

set_rgb(0, 20000, 50000)  # nice cyan/blue glow

# ── Push to display ──
print("Pushing to display...")
init_display()
show(buf)
print("Done! Artwork is live.")