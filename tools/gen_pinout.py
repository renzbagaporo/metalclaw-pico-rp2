#!/usr/bin/env python3
"""Generate the carrier pinout SVG from its netlist and a top-view PCB render.

Requires KiCad 9 and Pillow. Pass --board-image to reuse an existing orthographic
top render while adjusting the diagram; default operation makes a fresh render.
"""
from pathlib import Path
from collections import defaultdict, deque
import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PROJECT = 'metalclaw-pico-rp2'
PCB = ROOT / f'{PROJECT}.kicad_pcb'
SCH = ROOT / f'{PROJECT}.kicad_sch'
OUTPUT = ROOT / 'docs/images/pinout.svg'
COLORS = {'gpio': '#5b923a', 'carrier': '#344b64', 'SPI': '#c23c80',
          'UART': '#7552a3', 'UART_ALT': '#a188c0', 'I2C': '#2783b0',
          'PWM': '#8d7131', 'LPF': '#427e6b', 'power': '#cb4d48',
          'gnd': '#414957', 'control': '#ca6b7d', 'debug': '#c87425',
          'nc': '#8a929d', 'other': '#637183'}


def connections(netlist):
    root = ET.parse(netlist).getroot()
    nets = {n.get('name'): [dict(x.attrib) for x in n.findall('node')]
            for n in root.findall('./nets/net')}
    pin_net = {(n['ref'], n['pin']): name for name, nodes in nets.items() for n in nodes}
    rails = {'+3V3', '+3.3VP', 'GND', 'VS'}
    edges = defaultdict(list)
    for c in root.findall('./components/comp'):
        ref = c.get('ref')
        if not re.fullmatch(r'R\d+', ref):
            continue
        a, b = pin_net[ref, '1'], pin_net[ref, '2']
        if a not in rails and b not in rails:
            edges[a].append(b)
            edges[b].append(a)
    result = defaultdict(list)
    for name, nodes in nets.items():
        for n in nodes:
            m = re.match(r'GPIO(\d+)', n.get('pinfunction', ''))
            if n['ref'] != 'U2' or not m:
                continue
            gpio = int(m[1])
            queue, seen = deque([name]), {name}
            while queue:
                current = queue.popleft()
                for endpoint in nets[current]:
                    if endpoint['ref'] == 'A1':
                        result[endpoint['pin']].append(gpio)
                for nxt in edges[current]:
                    if nxt not in seen:
                        seen.add(nxt)
                        queue.append(nxt)
    result = {pin: sorted(set(gps)) for pin, gps in result.items()}
    gpio_pins = {pin: nodes for pin, nodes in result.items() if pin.isdigit()
                 and next(x for x in nets[pin_net['A1', pin]]
                          if x['ref'] == 'A1' and x['pin'] == pin).get('pinfunction', '').startswith('GPIO')}
    assert len(gpio_pins) == 26
    assert sum(map(len, gpio_pins.values())) == 43
    assert result['37'] == [1] and result['30'] == [9]
    assert result['D1'] == [17] and result['D3'] == [25]
    assert all(47 not in gs for gs in result.values())
    assert pin_net['A1', '39'] == pin_net['U1', '1'] == pin_net['D1', '1']
    assert pin_net['A1', '36'] == '+3.3VP'
    assert pin_net['A1', '35'].startswith('unconnected-')
    assert pin_net['A1', '40'].startswith('unconnected-')
    for hpin, upin in [('2', '34'), ('4', '33'), ('10', '35')]:
        assert pin_net['J2', hpin] == pin_net['U2', upin]
    assert all(pin_net['J2', p] == 'GND' for p in ['3', '5', '9'])
    return result


def calibrate(image):
    """Locate the 20 holes on each side to align labels with the actual render."""
    im = Image.open(image).convert('RGBA')
    w, h = im.size
    pix, seen, holes = im.load(), set(), []

    def dark(x, y):
        r, g, b, _ = pix[x, y]
        return max(r, g, b) < 8

    for y in range(80, h - 40):
        for x in range(55, w - 55):
            if (x, y) in seen or not dark(x, y):
                continue
            seen.add((x, y))
            queue, points = deque([(x, y)]), []
            while queue:
                a, b = queue.popleft()
                points.append((a, b))
                for c, d in [(a+1,b), (a-1,b), (a,b+1), (a,b-1)]:
                    if 55 <= c < w-55 and 80 <= d < h-40 and (c,d) not in seen and dark(c,d):
                        seen.add((c,d))
                        queue.append((c,d))
            if 250 < len(points) < 900:
                xs, ys = zip(*points)
                if max(xs)-min(xs) < 40 and max(ys)-min(ys) < 40:
                    holes.append((sum(xs)/len(xs), sum(ys)/len(ys)))
    left = sorted((p for p in holes if p[0] < w/4), key=lambda p: p[1])
    right = sorted((p for p in holes if p[0] > 3*w/4), key=lambda p: p[1])
    assert len(left) == len(right) == 20, 'Could not identify the forty header holes'
    sx = (sum(p[0] for p in right)-sum(p[0] for p in left))/20/17.78
    sy = ((left[-1][1]-left[0][1])+(right[-1][1]-right[0][1]))/2/48.26
    assert abs(sx-sy) < .04, 'Top render is not orthographic'
    # Current A1 inner holes: x=154.92/172.70; first y=74.74.
    pixel_left = sum(p[0] for p in left)/20 - 1.61*sx
    pixel_top = (left[0][1]+right[0][1])/2 - 1.37*sy
    residual = max(abs(p[1] - ((left[0][1]+right[0][1])/2+i*2.54*sy))
                   for col in [left, right] for i,p in enumerate(col))
    assert residual < .3
    return w, h, sx, sy, pixel_left, pixel_top, residual


def selected_functions():
    # Selected complementary carrier roles, checked against the RP2350 Bank-0 table.
    roles = {}
    for group in range(5):
        base, instance = 8*group, group % 2
        roles[base+3] = [f'SPI{instance} TX', f'UART{instance} RX']
        roles[base+4] = ['I2C0 SDA']
        roles[base+2] = [f'UART{instance} TX']
        roles[base+5] = [f'SPI{instance} CSn', 'I2C0 SCL']
        roles[base+6] = [f'SPI{instance} SCK', 'I2C1 SDA']
        roles[base] = [f'SPI{instance} RX']
        roles[base+7] = ['I2C1 SCL']
    roles.update({33:['GPIO / PIO'], 40:['I2C0 SDA'], 45:['UART0 RX'],
                  41:['SPI1 CSn', 'I2C0 SCL'], 46:['UART0 TX'], 42:['PWM9 A', 'LPF'],
                  43:['PWM9 B', 'LPF'], 44:['PWM10 A', 'LPF'],
                  1:['Power enable'], 9:['Target reset']})
    return roles


def make_svg(image, branches):
    w,h,sx,sy,px,py,residual = calibrate(image)
    scale = 320/21
    left, right, top = 510, 830, 150
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1340" height="1230" viewBox="0 0 1340 1230">',
             '<title>MetalClaw Pico RP2 pinout</title>',
             '<desc>Top view, USB at the top. Physical Pico-facing pins, connected RP2354B GPIO branches, selected carrier peripheral functions, target SWD and carrier J2 SWD.</desc>',
             '<rect width="1340" height="1230" fill="#fff"/>']
    metadata = {'pcb_sha256': hashlib.sha256(PCB.read_bytes()).hexdigest(),
                'schematic_sha256': hashlib.sha256(SCH.read_bytes()).hexdigest(),
                'carrier_gpio_branches': branches, 'hole_alignment_error_pixels': residual}
    parts.append('<metadata>'+html.escape(json.dumps(metadata,sort_keys=True))+'</metadata>')

    def text(x,y,label,size=16,fill='#253244',anchor='middle',weight=400):
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" text-anchor="{anchor}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(str(label))}</text>')

    def box(x,y,width,height,label,color,size=16):
        parts.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{width:.3f}" height="{height:.3f}" rx="3" fill="{color}"/>')
        text(x+width/2,y+height/2+size*.34,label,size,'#fff',weight=600)

    def line(points,color='#a4adba',width=1.3):
        parts.append('<polyline points="'+' '.join(f'{x:.3f},{y:.3f}' for x,y in points)+f'" fill="none" stroke="{color}" stroke-width="{width}"/>')

    def tag(x,y,label,color):
        width=16+len(label)*8.0
        box(x,y-9,width,18,label,color,13.5)
        return width

    text(30,42,'MetalClaw Pico RP2',29,anchor='start',weight=700)
    text(30,70,'Pinout',19,fill='#667184',anchor='start')
    text(670,113,'USB-C',15,weight=600)
    for x,label in [(185,'Selected carrier functions'),(346,'RP2354B'),(425,'Pico'),(480,'Pin'),
                    (860,'Pin'),(922,'Pico'),(1000,'RP2354B'),(1157,'Selected carrier functions')]:
        text(x,127,label,13,fill='#647184',weight=600)
    data=base64.b64encode(image.read_bytes()).decode()
    ix,iy=left-px*scale/sx,top-py*scale/sy
    parts.append(f'<image x="{ix}" y="{iy}" width="{w*scale/sx}" height="{h*scale/sy}" xlink:href="data:image/png;base64,{data}"/>')

    signals = {1:'GP0',2:'GP1',3:'GND',4:'GP2',5:'GP3',6:'GP4',7:'GP5',8:'GND',9:'GP6',10:'GP7',
               11:'GP8',12:'GP9',13:'GND',14:'GP10',15:'GP11',16:'GP12',17:'GP13',18:'GND',19:'GP14',20:'GP15',
               21:'GP16',22:'GP17',23:'GND',24:'GP18',25:'GP19',26:'GP20',27:'GP21',28:'GND',29:'GP22',30:'RUN',
               31:'GP26',32:'GP27',33:'AGND',34:'GP28',35:'ADC_VREF',36:'3V3_OUT',37:'3V3_EN',38:'GND',39:'VSYS',40:'VBUS'}
    roles=selected_functions()
    for pin in range(1,41):
        is_left=pin<=20
        index=pin-1 if is_left else 40-pin
        y=top+(1.37+index*2.54)*scale
        edge=left if is_left else right
        badge=480 if is_left else 860
        gx=386 if is_left else 880
        cx=316 if is_left else 972
        sig=signals[pin]
        kind='gnd' if sig in ['GND','AGND'] else 'control' if pin in [30,37] else 'power' if pin in [36,39,40] else 'nc' if pin==35 else 'gpio'
        line([(edge,y),(badge,y),(gx+78 if is_left else gx,y)])
        parts.append(f'<circle cx="{badge}" cy="{y}" r="12" fill="#edf0f4"/>')
        text(badge,y+4.5,pin,13,weight=600)
        if pin in [31,32,34]:
            box(gx,y-17,78,34,'',COLORS['LPF'])
            text(gx+39,y-1,sig,16,'#fff',weight=600)
            text(gx+39,y+12,{31:'ADC0',32:'ADC1',34:'ADC2'}[pin],11,'#fff')
        else:
            box(gx,y-12,78,24,sig,COLORS[kind],13 if len(sig)>6 else 16)
        gps=branches.get(str(pin),[])
        for n,gp in enumerate(gps):
            yy=y+(n-(len(gps)-1)/2)*20
            box(cx,yy-9,60,18,f'GP{gp}',COLORS['carrier'],13.5)
            labels=roles.get(gp,['GPIO / PIO'])
            widths=[16+len(label)*8 for label in labels]
            start=302-sum(widths)-5*(len(labels)-1) if is_left else 1044
            for label,width in zip(labels,widths):
                color=COLORS['SPI'] if label.startswith('SPI') else COLORS['UART_ALT' if gp%4 in [2,3] else 'UART'] if label.startswith('UART') else COLORS['I2C'] if label.startswith('I2C') else COLORS['PWM'] if label.startswith('PWM') else COLORS['LPF'] if label=='LPF' else COLORS['control'] if gp in [1,9] else COLORS['other']
                tag(start,yy,label,color);start+=width+5
        if pin in [35,40]:
            box(cx,y-9,60,18,'NC',COLORS['nc'],13.5)
            tag(1044,y,'Not connected',COLORS['nc'])
        if pin in [36,39]:
            tag(1044,y,'Target pull-ups' if pin==36 else 'Shared supply',COLORS['power'])

    # Physical SWD contacts are D1/D2/D3, left to right, at the bottom edge.
    bottom=top+51*scale
    for name,gpio,source_x,x in [('SWCLK',17,161.27,526),('GND',None,163.81,670),('SWDIO',25,166.35,814)]:
        src=left+(source_x-153.31)*scale
        line([(src,bottom),(src,944),(x,967),(x,980)],COLORS['gnd' if gpio is None else 'debug'],1.6)
        box(x-52,982,104,25,name,COLORS['gnd' if gpio is None else 'debug'])
        if gpio is not None:text(x,1028,f'Carrier GP{gpio}',14,fill=COLORS['carrier'],weight=600)
    text(670,1060,'Target SWD contacts',14,fill='#647184')

    # J2 is drawn in its actual top-view orientation: pin 1 at upper right.
    text(1115,938,'J2 · carrier SWD',18,weight=700)
    for row,nums in enumerate([[9,7,5,3,1],[10,8,6,4,2]]):
        for col,pin in enumerate(nums):
            label={1:'3V3',2:'SWDIO',3:'GND',4:'SWCLK',5:'GND',6:'NC',7:'NC',8:'NC',9:'GND',10:'RESET'}[pin]
            x=970+col*69;y=987+row*57
            color=COLORS['power'] if pin==1 else COLORS['gnd'] if label=='GND' else COLORS['nc'] if label=='NC' else COLORS['debug']
            box(x-19,y-13,38,26,pin,color,14)
            text(x,y-23 if row==0 else y+32,label,12,fill='#39465a',weight=600)
    text(1110,1095,'Top view · pin 1 at upper right',12,fill='#647184')

    text(185,956,'On-board controls',17,weight=700)
    text(185,985,'SW1: carrier BOOTSEL',15)
    text(185,1012,'SW2: carrier RESET',15)
    text(185,1046,'Target RUN: carrier GP9',14,fill=COLORS['control'])
    text(185,1071,'Target 3V3_EN: carrier GP1',14,fill=COLORS['control'])
    # Small labels identify the otherwise unmarked controls in the top render.
    for label,x,y in [('SW1',159.935,112.3),('SW2',167.475,112.3),('J2',163.81,120.0)]:
        dx=left+(x-153.31)*scale;dy=top+(y-73.37)*scale
        box(dx-18,dy-9,36,18,'','#f1f4f7',11)
        text(dx,dy+4,label,11,'#344252',weight=700)

    line([(30,1120),(1310,1120)],'#d9dee6')
    legend=[('GPIO','gpio'),('Carrier GPIO','carrier'),('SPI','SPI'),('UART','UART'),('UART alt','UART_ALT'),('I2C','I2C'),('Filtered PWM','LPF'),('Power','power'),('Ground','gnd'),('Control','control'),('SWD','debug'),('NC','nc')]
    x=30
    for label,kind in legend:
        parts.append(f'<rect x="{x}" y="1138" width="12" height="12" rx="2" fill="{COLORS[kind]}"/>')
        text(x+18,1149,label,12,anchor='start');x+=len(label)*6.3+34
    text(30,1181,'Pin numbers and Pico labels refer to the target interface. GP numbers in the RP2354B columns belong to the carrier.',14,anchor='start')
    text(30,1205,'Selected carrier functions shown. Unused branches: inputs, pulls off. Only one push-pull driver per target net.',13,fill='#647184',anchor='start')
    parts.append('</svg>')
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text('\n'.join(parts)+'\n')
    return metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board-image',type=Path)
    args=parser.parse_args()
    cli=shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
    with tempfile.TemporaryDirectory(prefix='metalclaw-pinout-') as tmp:
        netlist=Path(tmp)/'netlist.xml'
        subprocess.run([cli,'sch','export','netlist','--format','kicadxml','--output',str(netlist),str(SCH)],check=True)
        image=args.board_image or Path(tmp)/'board.png'
        if args.board_image is None:
            subprocess.run([cli,'pcb','render','--side','top','--quality','basic','--width','640','--height','1500',
                            '--background','transparent','--zoom','0.90','--output',str(image),str(PCB)],check=True)
        metadata=make_svg(image,connections(netlist))
        print(f'Generated {OUTPUT.relative_to(ROOT)}; 40 header pins, 43 GPIO branches, 4 control/debug branches.')
        print(f'Maximum render alignment error: {metadata["hole_alignment_error_pixels"]:.3f} px')


if __name__=='__main__':
    main()
