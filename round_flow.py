"""
Fluid flow — full 240x240, optimized for ~16+ fps
Precomputed colors, fast framebuf circle primitives
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc

CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(0)
MISO = Pin(12, Pin.IN)
spi = SPI(1, baudrate=62_500_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=MISO)

W, H, CX, CY = 240, 240, 120, 120

def cmd(b, *d):
    DC(0); CS(0); spi.write(bytes([b])); CS(1)
    if d: DC(1); CS(0); spi.write(bytes(d)); CS(1)

# Init
RST(0); time.sleep_ms(50); RST(1); time.sleep_ms(150)
cmd(0xEF); cmd(0xEB, 0x14)
cmd(0xFE); cmd(0xEF); cmd(0xEB, 0x14)
cmd(0x3A, 0x55); cmd(0x36, 0x00); cmd(0x21)
cmd(0x11); time.sleep_ms(120)
cmd(0x29); time.sleep_ms(100)
BL.duty_u16(65535)

buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)
cmd(0x2A, 0x00,0x00,0x00,0xEF)
cmd(0x2B, 0x00,0x00,0x00,0xEF)

def rgb(r,g,b):
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

# Precompute 256-color rainbow palette
PAL = [0]*256
for i in range(256):
    a = i * math.pi / 128.0
    PAL[i] = rgb(
        int(127+127*math.sin(a)),
        int(127+127*math.sin(a+2.094)),
        int(127+127*math.sin(a+4.189))
    )

frame = 0
fc = 0; ft = time.ticks_ms()

print('FLUID FLOW')

while True:
    t = frame & 0xFF
    
    # 12 concentric pulsing rings
    for i in range(12):
        r = 10 + i * 10
        pulse = int(math.sin((t*3 + i*20) * math.pi / 128.0) * 5)
        r += pulse
        c = PAL[((i*21 + t*3) & 0xFF)]
        fb.ellipse(CX, CY, r, r, c, True)
    
    # 5 orbiting bright spots
    for i in range(5):
        ang = ((t * (2+i) + i * 51) & 0xFF) * math.pi / 128.0
        dist = 30 + 50 * (1 + math.sin((t*4 + i*30) * math.pi / 128.0)) / 2
        sx = CX + int(dist * math.cos(ang))
        sy = CY + int(dist * math.sin(ang))
        rad = 3 + i
        c = PAL[((t*2 + i*40) & 0xFF)]
        fb.ellipse(sx, sy, rad, rad, rgb(255,255,255), True)
        # Glow ring
        fb.ellipse(sx, sy, rad+4, rad+4, c, False)
    
    # Push
    cmd(0x2C)
    CS(0); DC(1); spi.write(buf); CS(1)
    
    frame += 1; fc += 1
    
    now = time.ticks_ms()
    if time.ticks_diff(now, ft) >= 2000:
        e = time.ticks_diff(now, ft) / 1000.0
        print(f'  {fc/e:.0f} fps')
        fc = 0; ft = now; gc.collect()