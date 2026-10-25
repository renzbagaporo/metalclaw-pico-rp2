#!/usr/bin/env python3
"""Generate the JLCPCB fabrication package for metalclaw-pico-rp2.

Produces, under fab/:
  gerbers/          gerbers + Excellon drill + job file
  <project>_gerbers.zip
  BOM_jlcpcb.csv    Comment, Designator, Footprint, LCSC Part #
  CPL_jlcpcb.csv    Designator, Mid X, Mid Y, Layer, Rotation
  <project>_assembly-review.zip  upload files, source provenance and licensing
  SOURCE.json      sheet revision, Git source state and source-file hashes
  SHA256SUMS       checksums for the generated files

Designators excluded from the CPL are those with no physical part to place:
  A1    the board-outline/castellated-contact footprint, not a component
  NT*   net ties - bare copper joining two nets, nothing to assemble
  TP*   test points - bare copper pads, nothing to assemble
The BOM lists only parts carrying an LCSC field, which excludes the same set.
The two files are cross-checked: their designator sets must be identical.

Usage:  python3 tools/gen_fab.py
"""
import csv
import hashlib
import json
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

KICAD_CLI = (shutil.which('kicad-cli') or
             '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')

LAYERS = ('F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,'
          'F.Silkscreen,B.Silkscreen,Edge.Cuts')

# Designators that are copper features, not placeable components.
NOT_PLACED = re.compile(r'^(A1|NT\d+|TP\d+)$')

# Measured against JLC's placement preview for these exact selected parts.
# JLC CPL angles are positive counterclockwise; these offsets reconcile its
# library zero angles with KiCad, without rotating the source footprints.
# Ref + purchasing-code guards require a new review after a part substitution.
CPL_ROTATION_OFFSETS = {
    'U1': ('C51118', -90.0),
    'U3': ('C5333729', -90.0),
    'L1': ('C42411119', 180.0),
    'J2': ('C27985146', -90.0),
}

# Placement heads in the exact selected JLCEDA/EasyEDA packages differ from
# the KiCad body origins. Offsets are in exported CPL X/Y, not PCB screen Y.
# J1 is derived from its signal row and independently checked against both
# locating pegs and all four shell anchors. D1 is checked against both lands.
# A new JLC preview must confirm the runtime library registration
# before the assembly is approved.
# ref: (purchasing code, reviewed raw KiCad angle, delta X, delta Y)
CPL_POSITION_OFFSETS = {
    'J1': ('C52209111', 180.0, 0.0, -1.3182),
    'D1': ('C172430', 90.0, 0.0, 0.3000),
}


def jlc_rotation(ref, raw_rotation, lcsc):
    if ref not in CPL_ROTATION_OFFSETS:
        return raw_rotation
    expected_lcsc, offset = CPL_ROTATION_OFFSETS[ref]
    if lcsc != expected_lcsc:
        raise ValueError(f'{ref}: rotation correction expects {expected_lcsc}, '
                         f'found {lcsc!r}; review the new part orientation')
    return f'{(float(raw_rotation) + offset) % 360:.6f}'


def jlc_position(ref, raw_x, raw_y, raw_rotation, lcsc):
    x, y = float(raw_x), float(raw_y)
    if ref in CPL_POSITION_OFFSETS:
        expected_lcsc, angle, dx, dy = CPL_POSITION_OFFSETS[ref]
        if lcsc != expected_lcsc or abs(
                (float(raw_rotation) - angle + 180) % 360 - 180) > 1e-6:
            raise ValueError(f'{ref}: position correction expects {expected_lcsc} '
                             f'at {angle:g} degrees; review the new placement')
        x += dx
        y += dy
    return f'{x:.4f}mm', f'{y:.4f}mm'


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'command failed: {" ".join(args)}\n{r.stdout}{r.stderr}')
    return r.stdout


def hardware_revision():
    revisions = []
    for path in (SCH, PCB):
        block = re.search(r'^\t\(title_block\n(.*?)^\t\)',
                          path.read_text(), re.MULTILINE | re.DOTALL)
        revision = re.search(r'\(rev "([^"]+)"\)', block[1]) if block else None
        if not revision:
            sys.exit(f'missing sheet revision in {path.name}')
        revisions.append(revision[1])
    if revisions[0] != revisions[1]:
        sys.exit(f'schematic/PCB revision mismatch: {revisions}')
    label = re.search(r'\(gr_text "metalclaw\\npico-rp2\\n([^"]+)"',
                      PCB.read_text())
    if not label or label[1] != revisions[0]:
        sys.exit('PCB silkscreen revision does not match the sheet revision')
    return revisions[0]


def write_provenance(revision):
    paths = [SCH, PCB, ROOT / f'{PROJECT}.kicad_pro',
             ROOT / f'{PROJECT}.kicad_dru', ROOT / 'fp-lib-table',
             Path(__file__).resolve(), ROOT / 'tools/gen_j2_model.py',
             ROOT / 'LICENSE', ROOT / 'NOTICE.md']
    for folder in ('footprints', '3dmodels'):
        paths.extend(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and p.suffix in ('.kicad_mod', '.step', '.wrl'))
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True)
    status = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain'],
                            capture_output=True, text=True)
    metadata = {
        'project': PROJECT,
        'hardware_revision': revision,
        'placement_corrections': {
            'rotation_offsets': CPL_ROTATION_OFFSETS,
            'position_offsets_cpl_frame': CPL_POSITION_OFFSETS,
            'jlc_reimport_confirmation': 'pending',
        },
        'git_commit': commit.stdout.strip() if commit.returncode == 0 else None,
        'working_tree_dirty': bool(status.stdout.strip()) if status.returncode == 0 else None,
        'source_sha256': {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)
        },
    }
    (FAB / 'SOURCE.json').write_text(json.dumps(metadata, indent=2) + '\n')


def write_checksums():
    paths = sorted(p for p in FAB.rglob('*')
                   if p.is_file() and p.name != 'SHA256SUMS')
    (FAB / 'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(FAB).as_posix()}\n'
        for p in paths))


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
    components = ET.parse(FAB / 'net_bom.xml').getroot()
    purchasing_codes = {
        comp.get('ref'): next((f.text or '' for f in comp.iter('field')
                              if f.get('name') == 'LCSC'), '')
        for comp in components.iter('comp')
    }
    rows = []
    with open(FAB / 'pos_raw.csv') as fh:
        for row in csv.DictReader(fh):
            ref = row['Ref']
            if ref.startswith('#') or NOT_PLACED.match(ref):
                continue
            if ref in (CPL_ROTATION_OFFSETS.keys() | CPL_POSITION_OFFSETS.keys()) and row['Side'] != 'top':
                raise ValueError(f'{ref}: placement correction was reviewed for Top only')
            x, y = jlc_position(ref, row['PosX'], row['PosY'], row['Rot'],
                                purchasing_codes.get(ref, ''))
            rows.append([ref, x, y,
                         'Top' if row['Side'] == 'top' else 'Bottom',
                         jlc_rotation(ref, row['Rot'],
                                      purchasing_codes.get(ref, ''))])
    rows.sort()
    refs = {r[0] for r in rows}
    if missing := (CPL_ROTATION_OFFSETS.keys() | CPL_POSITION_OFFSETS.keys()) - refs:
        raise ValueError(f'placement-reviewed components absent from CPL: {sorted(missing)}')
    return rows, refs


def bundle_assembly_review():
    """Bundle the upload files with provenance and licensing."""
    paths = [FAB / f'{PROJECT}_gerbers.zip',
             FAB / 'BOM_jlcpcb.csv', FAB / 'CPL_jlcpcb.csv', FAB / 'SOURCE.json',
             ROOT / 'LICENSE', ROOT / 'NOTICE.md']
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.is_file()]
    if missing:
        sys.exit(f'assembly package inputs missing: {missing}')
    with zipfile.ZipFile(FAB / f'{PROJECT}_assembly-review.zip', 'w',
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT).as_posix())


def main():
    revision = hardware_revision()
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
    write_provenance(revision)
    bundle_assembly_review()
    write_checksums()

    drill = (GERBERS / f'{PROJECT}.drl').read_text()
    round_holes = re.findall(r'^X[\d.-]+Y[\d.-]+$', drill, re.MULTILINE)
    slots = re.findall(r'^X[\d.-]+Y[\d.-]+G85X[\d.-]+Y[\d.-]+$',
                       drill, re.MULTILINE)
    print(f'BOM   {len(bom_rows)} lines, {len(bom_refs)} placed parts')
    print(f'rev   {revision}; '
          'provenance: fab/SOURCE.json; checksums: fab/SHA256SUMS')
    print(f'CPL   {len(cpl_rows)} placements, sides: '
          f'{sorted({r[3] for r in cpl_rows})}')
    print(f'excluded from both (no physical part): {skipped}')
    print(f'drill {len(round_holes)} round holes + {len(slots)} slots '
          f'({len(round_holes) + len(slots)} features)')


if __name__ == '__main__':
    main()
