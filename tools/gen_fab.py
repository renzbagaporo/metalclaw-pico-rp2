#!/usr/bin/env python3
"""Generate the JLCPCB fabrication package for metalclaw-pico-rp2.

Produces, under fab/:
  gerbers/          gerbers + Excellon drill + job file
  <project>_gerbers.zip
  BOM_jlcpcb.csv    Comment, Designator, Footprint, LCSC Part #
  CPL_jlcpcb.csv    Designator, Mid X, Mid Y, Layer, Rotation
  <project>_assembly-review.zip  upload files plus assembly instructions/drawings

Designators excluded from the CPL are those with no physical part to place:
  A1    the board-outline/castellated-contact footprint, not a component
  NT*   net ties - bare copper joining two nets, nothing to assemble
  TP*   test points - bare copper pads, nothing to assemble
The BOM lists only parts carrying an LCSC field, which excludes the same set.
The two files are cross-checked: their designator sets must be identical.

Usage:  python3 tools/gen_fab.py
"""
import csv
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = 'metalclaw-pico-rp2'
PCB = ROOT / f'{PROJECT}.kicad_pcb'
SCH = ROOT / f'{PROJECT}.kicad_sch'
FAB = ROOT / 'fab'
GERBERS = FAB / 'gerbers'

KICAD_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'

LAYERS = ('F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,'
          'F.Silkscreen,B.Silkscreen,Edge.Cuts')

# Designators that are copper features, not placeable components.
NOT_PLACED = re.compile(r'^(A1|NT\d+|TP\d+)$')


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'command failed: {" ".join(args)}\n{r.stdout}{r.stderr}')
    return r.stdout


def export():
    if FAB.exists():
        shutil.rmtree(FAB)
    GERBERS.mkdir(parents=True)
    run(KICAD_CLI, 'pcb', 'export', 'gerbers', '--layers', LAYERS,
        '--output', str(GERBERS) + '/', str(PCB))
    run(KICAD_CLI, 'pcb', 'export', 'drill', '--format', 'excellon',
        '--excellon-units', 'mm', '--drill-origin', 'absolute',
        '--output', str(GERBERS) + '/', str(PCB))
    run(KICAD_CLI, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
        '--side', 'both', '--output', str(FAB / 'pos_raw.csv'), str(PCB))
    run(KICAD_CLI, 'sch', 'export', 'netlist', '--format', 'kicadxml',
        '--output', str(FAB / 'net_bom.xml'), str(SCH))


def build_bom():
    """Group placed parts by LCSC number. Returns (rows, designators, skipped)."""
    root = ET.parse(FAB / 'net_bom.xml').getroot()
    groups, skipped = {}, []
    for comp in root.iter('comp'):
        ref = comp.get('ref')
        if ref.startswith('#'):
            continue
        fields = {f.get('name'): (f.text or '') for f in comp.iter('field')}
        lcsc = fields.get('LCSC', '')
        if not lcsc:
            skipped.append(ref)
            continue
        g = groups.setdefault(lcsc, {'refs': [], 'val': '', 'fp': ''})
        g['refs'].append(ref)
        # 'LCSC MPN' records an approved substitute when the Mouser part
        # (the hand-build source) is not the part JLC will actually fit.
        g['val'] = fields.get('LCSC MPN') or (comp.findtext('value') or '')
        g['fp'] = (comp.findtext('footprint') or '').split(':')[-1]

    rows = [[g['val'], ','.join(sorted(g['refs'])), g['fp'], lcsc]
            for lcsc, g in sorted(groups.items(), key=lambda kv: kv[1]['refs'][0])]
    designators = {r for g in groups.values() for r in g['refs']}
    return rows, designators, sorted(skipped)


def build_cpl():
    rows = []
    with open(FAB / 'pos_raw.csv') as fh:
        for row in csv.DictReader(fh):
            ref = row['Ref']
            if ref.startswith('#') or NOT_PLACED.match(ref):
                continue
            rows.append([ref,
                         f"{float(row['PosX']):.4f}mm",
                         f"{float(row['PosY']):.4f}mm",
                         'Top' if row['Side'] == 'top' else 'Bottom',
                         row['Rot']])
    rows.sort()
    return rows, {r[0] for r in rows}


def bundle_assembly_review():
    """Keep instructions beside the BOM/CPL and the separate Gerber upload ZIP."""
    paths = [FAB / f'{PROJECT}_gerbers.zip',
             FAB / 'BOM_jlcpcb.csv', FAB / 'CPL_jlcpcb.csv']
    paths += [ROOT / name for name in
              ('JLCPCB_ASSEMBLY.md', 'JLCPCB_SOURCING.md', 'JLCPCB_DFM_REVIEW.md')]
    for folder in ('docs/assembly', 'docs/dfm'):
        paths.extend(sorted(p for p in (ROOT / folder).rglob('*') if p.is_file()))
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing:
        sys.exit(f'assembly package inputs missing: {missing}')
    with zipfile.ZipFile(FAB / f'{PROJECT}_assembly-review.zip', 'w',
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())


def main():
    export()
    bom_rows, bom_refs, skipped = build_bom()
    cpl_rows, cpl_refs = build_cpl()

    # A mismatch means either a placed part is missing an LCSC number, or a
    # copper-only feature is about to be sent to the pick-and-place.
    if bom_refs != cpl_refs:
        sys.exit(f'BOM/CPL designator mismatch\n'
                 f'  only in BOM: {sorted(bom_refs - cpl_refs)}\n'
                 f'  only in CPL: {sorted(cpl_refs - bom_refs)}')

    with open(FAB / 'BOM_jlcpcb.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        w.writerows(bom_rows)
    with open(FAB / 'CPL_jlcpcb.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(cpl_rows)

    (FAB / 'net_bom.xml').unlink()
    (FAB / 'pos_raw.csv').unlink()
    shutil.make_archive(str(FAB / f'{PROJECT}_gerbers'), 'zip', str(GERBERS))
    bundle_assembly_review()

    drill = (GERBERS / f'{PROJECT}.drl').read_text()
    round_holes = re.findall(r'^X[\d.-]+Y[\d.-]+$', drill, re.MULTILINE)
    slots = re.findall(r'^X[\d.-]+Y[\d.-]+G85X[\d.-]+Y[\d.-]+$',
                       drill, re.MULTILINE)
    print(f'BOM   {len(bom_rows)} lines, {len(bom_refs)} placed parts')
    print(f'CPL   {len(cpl_rows)} placements, sides: '
          f'{sorted({r[3] for r in cpl_rows})}')
    print(f'excluded from both (no physical part): {skipped}')
    print(f'drill {len(round_holes)} round holes + {len(slots)} slots '
          f'({len(round_holes) + len(slots)} features)')


if __name__ == '__main__':
    main()
