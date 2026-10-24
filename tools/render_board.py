#!/usr/bin/env python3
"""Render the README image directly from the PCB with KiCad's raytracer."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / 'metalclaw-pico-rp2.kicad_pcb'
OUTPUT = ROOT / 'docs/images/board-v1.r1.png'


def main():
    cli = shutil.which('kicad-cli')
    if cli is None:
        candidate = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
        if candidate.is_file():
            cli = str(candidate)
    if cli is None:
        sys.exit('Install KiCad 9 and put kicad-cli on PATH.')

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        cli, 'pcb', 'render',
        '--quality', 'high', '--width', '1800', '--height', '1200',
        '--background', 'opaque', '--floor', '--perspective',
        # 325 degrees is -35; positive angles avoid CLI option parsing issues.
        '--rotate', '325,0,60', '--zoom', '0.98',
        '--output', str(OUTPUT), str(PCB),
    ], cwd=ROOT, check=True)
    print(f'Rendered {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
