"""
Spinning Earth globe — @micropython.viper upscale for 8fps
8 pre-rendered frames at 120×120, native 2x upscale
"""
from machine import Pin, SPI, PWM
import time, framebuf, math, gc, array, micropython

CS  = Pin(9,  Pin.OUT, value=1)
DC  = Pin(8,  Pin.OUT, value=0)
RST = Pin(12, Pin.OUT, value=1)
BL  = PWM(Pin(13)); BL.freq(1000); BL.duty_u16(0)
MISO = Pin(12, Pin.IN)
spi = SPI(1, baudrate=62_500_000, polarity=0, phase=0,
          sck=Pin(10), mosi=Pin(11), miso=MISO)

def cmd(b, *d):
    DC(0); CS(0); spi.write(bytes([b])); CS(1)
    if d: DC(1); CS(0); spi.write(bytes(d)); CS(1)

RST(0); time.sleep_ms(50); RST(1); time.sleep_ms(150)
cmd(0xEF); cmd(0xEB, 0x14)
cmd(0xFE); cmd(0xEF); cmd(0xEB, 0x14)
cmd(0x3A, 0x55); cmd(0x36, 0x00); cmd(0x21)
cmd(0x11); time.sleep_ms(120)
cmd(0x29); time.sleep_ms(100)
BL.duty_u16(65535)

W, H, FW, FH = 240, 240, 120, 120
buf = bytearray(W * H * 2)
cmd(0x2A, 0x00,0x00,0x00,0xEF)
cmd(0x2B, 0x00,0x00,0x00,0xEF)

def rgb565(r,g,b):
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

# ── Earth texture ──
print('Texture...')
TX_W, TX_H = 180, 90
tex = bytearray(TX_W * TX_H)
for ty in range(TX_H):
    lat = (ty-TX_H/2)/(TX_H/2)
    for tx in range(TX_W):
        lon=tx/TX_W; v=0
        v+=math.sin((lon-.16)*8)*math.cos(lat*2.5+.4)*.28
        v+=math.sin((lon-.22)*6)*math.sin(lat*1.5+1.2)*.32
        v+=math.sin((lon-.48)*5)*math.cos(lat*3-.3)*.30
        v+=math.sin((lon-.62)*7+math.sin(lat*4)*2)*.28
        v+=math.exp(-((lon-.72)**2+(lat+.35)**2)*35)*.45
        v+=math.exp(-((lat+.82)**2)*25)*.5
        v+=math.exp(-((lat-.82)**2)*25)*.3
        tex[ty*TX_W+tx]=1 if v>.09 else 0
gc.collect()

# Colors
LAND=array.array('H',[0]*256); OCEAN=array.array('H',[0]*256)
for s in range(256):
    f=s/255
    LAND[s]=rgb565(int(35*f),int(130*f),int(55*f))
    OCEAN[s]=rgb565(int(10*f),int(25*f),int(70*f))
gc.collect()

# Render frames
N=8; FS=FW*FH*2
FRAMES=[None]*N
print(f'Rendering {N} frames...')
for fi in range(N):
    rot=fi*TX_W//N
    fb_data=bytearray(FS)
    fb2=framebuf.FrameBuffer(fb_data,FW,FH,framebuf.RGB565)
    for y in range(FH):
        dy=y-60; dy2=dy*dy
        if dy2>3600:continue
        hw=int(math.sqrt(3600-dy2))
        for x in range(60-hw,61+hw):
            dx=x-60
            dz=math.sqrt(3600-dx*dx-dy2)
            lat_a=math.asin(dy/60.0)
            ty=int((lat_a/math.pi+.5)*TX_H)
            if ty<0:ty=0
            if ty>=TX_H:ty=TX_H-1
            tx=int(math.atan2(dx,dz)/(2*math.pi)*TX_W+rot)%TX_W
            s=int((0.45+0.55*max(0,dz/60.0))*255)
            if tex[ty*TX_W+tx]:fb2.pixel(x,y,LAND[s])
            else:fb2.pixel(x,y,OCEAN[s])
    FRAMES[fi]=fb_data
    if fi%3==0:print(f'  {fi+1}/{N}')
    gc.collect()

# ── Viper upscale: 120×120 → 240×240 pixel-doubling ──
@micropython.viper
def upscale2x(dst: ptr8, src: ptr8, fw: int, w: int):
    """Native 2x upscale. Each src pixel → 2×2 dst pixels."""
    for sy in range(fw):
        sr = sy * fw * 2
        dr0 = sy * 2 * w * 2
        dr1 = dr0 + w * 2
        for sx in range(fw):
            so = sr + sx * 2
            lo = src[so]
            hi = src[so + 1]
            do0 = dr0 + sx * 4
            do1 = dr1 + sx * 4
            dst[do0] = lo; dst[do0+1] = hi
            dst[do0+2] = lo; dst[do0+3] = hi
            dst[do1] = lo; dst[do1+1] = hi
            dst[do1+2] = lo; dst[do1+3] = hi

# ── Playback ──
print('Spinning!')
frame=0; fc=0; ft=time.ticks_ms()

while True:
    fi = frame % N
    upscale2x(buf, FRAMES[fi], FW, W)
    
    cmd(0x2C); CS(0); DC(1); spi.write(buf); CS(1)
    frame+=1; fc+=1
    
    now=time.ticks_ms()
    if time.ticks_diff(now,ft)>=3000:
        e=time.ticks_diff(now,ft)/1000.0
        print(f'  {fc/e:.0f} fps')
        fc=0; ft=now