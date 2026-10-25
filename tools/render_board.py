#!/usr/bin/env python3
"""Render the README image directly from the PCB with KiCad's raytracer."""
from pathlib import Path
from contextlib import contextmanager
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / 'metalclaw-pico-rp2.kicad_pcb'
OUTPUT = ROOT / 'docs/images/board-v1.r1.png'


@contextmanager
def render_source():
    """Show the selected ENIG finish without changing the manufacturing CAD."""
    with tempfile.NamedTemporaryFile(suffix='.kicad_pcb', prefix='.readme-render-',
                                     dir=ROOT, delete=False) as handle:
        path = Path(handle.name)
        source = PCB.read_text()
        handle.write(source.replace('(copper_finish "None")',
                                    '(copper_finish "ENIG")', 1).encode())
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def main():
    cli = shutil.which('kicad-cli')
    if cli is None:
        candidate = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
        if candidate.is_file():
            cli = str(candidate)
    if cli is None:
        sys.exit('Install KiCad 9 and put kicad-cli on PATH.')

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with render_source() as source:
        subprocess.run([
        cli, 'pcb', 'render', '--define-var', f'KIPRJMOD={ROOT}',
        '--quality', 'high', '--width', '1800', '--height', '1200',
        '--background', 'opaque', '--floor', '--perspective',
        # 325 degrees is -35; positive angles avoid CLI option parsing issues.
        '--rotate', '325,0,60', '--zoom', '0.98',
        '--output', str(OUTPUT), str(source),
        ], cwd=ROOT, check=True)
    print(f'Rendered {OUTPUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
