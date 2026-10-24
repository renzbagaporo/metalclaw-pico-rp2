#!/usr/bin/env python3
"""Generate the original, unbranded SS14HE package model without opening a GUI.

Run with FreeCAD's bundled Python, e.g. on macOS:
  /Applications/FreeCAD.app/Contents/Resources/bin/python tools/gen_d1_model.py

Package envelope follows TECH PUBLIC SS14HE, outline drawing SOD323HE.
Body is 2.00 x 1.30 mm; total height including marking is 0.680 mm.
Metal span is 2.60 mm. Contacts are 1.65 x 0.80 and 0.45 x 0.60 mm,
within the drawing's ranges and aligned to the unchanged 0.50-mm land gap.
Mold draft, stripe and colors are representative, not supplier CAD data.
"""
from pathlib import Path
import re
import sys

FREECAD_LIB = Path('/Applications/FreeCAD.app/Contents/Resources/lib')
if FREECAD_LIB.is_dir():
    sys.path.insert(0, str(FREECAD_LIB))
import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '3dmodels'
NAME = 'D_SOD-323HE_SS14HE'


def rectangle(x, y, z):
    return Part.makePolygon([App.Vector(-x, -y, z), App.Vector(x, -y, z),
                             App.Vector(x, y, z), App.Vector(-x, y, z),
                             App.Vector(-x, -y, z)])


def color_step(path, colors):
    """Add standard AP214 presentation styles to the headless STEP export."""
    text = path.read_text()
    solids = re.findall(r'#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\(', text)
    assert len(solids) == len(colors)
    context = re.search(r'GEOMETRIC_REPRESENTATION_CONTEXT\(3\)', text)
    assert context
    context_id = re.findall(r'#(\d+)\s*=', text[:context.start()])[-1]
    next_id = max(map(int, re.findall(r'#(\d+)\s*=', text))) + 1
    records = []
    styled = []

    def add(value):
        nonlocal next_id
        result = f'#{next_id}'
        records.append(f'{result}={value};')
        next_id += 1
        return result

    for solid, rgb in zip(solids, colors):
        c = add("COLOUR_RGB('',%s)" % ','.join(str(v) for v in rgb))
        fill_color = add(f"FILL_AREA_STYLE_COLOUR('',{c})")
        fill = add(f"FILL_AREA_STYLE('',({fill_color}))")
        surface = add(f'SURFACE_STYLE_FILL_AREA({fill})')
        side = add(f"SURFACE_SIDE_STYLE('',({surface}))")
        usage = add(f'SURFACE_STYLE_USAGE(.BOTH.,{side})')
        assignment = add(f'PRESENTATION_STYLE_ASSIGNMENT(({usage}))')
        styled.append(add(f"STYLED_ITEM('',({assignment}),#{solid})"))
    add("MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('',"
        f"({','.join(styled)}),#{context_id})")
    text = text.replace('ENDSEC;\nEND-ISO-10303-21;',
                        '\n'.join(records) + '\nENDSEC;\nEND-ISO-10303-21;')
    assert 'COLOUR_RGB' in text
    path.write_text('\n'.join(line.rstrip() for line in text.splitlines()) + '\n')


def main():
    OUT.mkdir(exist_ok=True)
    body = Part.makeLoft([rectangle(1.0, 0.65, 0.15),
                          rectangle(0.925, 0.575, 0.675)], True)
    cathode = Part.makeBox(1.65, 0.80, 0.15, App.Vector(-1.30, -0.40, 0))
    anode = Part.makeBox(0.45, 0.60, 0.15, App.Vector(0.85, -0.30, 0))
    stripe = Part.makeBox(0.20, 1.00, 0.005, App.Vector(-0.80, -0.50, 0.675))
    shapes = [body, cathode, anode, stripe]
    colors = [(0.075, 0.080, 0.085), (0.72, 0.74, 0.76),
              (0.72, 0.74, 0.76), (0.78, 0.79, 0.80)]
    for shape in shapes:
        assert shape.isValid() and shape.Volume > 0
    whole = Part.makeCompound(shapes)
    assert abs(whole.BoundBox.XLength - 2.60) < 1e-7
    assert abs(whole.BoundBox.YLength - 1.30) < 1e-7
    assert abs(whole.BoundBox.ZLength - 0.680) < 1e-7
    step = OUT / (NAME + '.step')
    # A compound preserves the order used by the accompanying color styles.
    whole.exportStep(str(step))
    color_step(step, colors)
    restored = Part.read(str(step))
    assert restored.isValid() and len(restored.Solids) == 4
    assert abs(restored.BoundBox.XLength - 2.60) < 1e-6
    lines = ['#VRML V2.0 utf8',
             '# Original SS14HE SOD-323HE model; millimetres / 2.54 for KiCad VRML.',
             '# Cathode is negative X. See tools/gen_d1_model.py for dimensions.']
    for shape, rgb in zip(shapes, colors):
        vertices, triangles = shape.tessellate(0.01)
        points = ',\n'.join('      %.9f %.9f %.9f' %
                            (v.x / 2.54, v.y / 2.54, v.z / 2.54) for v in vertices)
        faces = ',\n'.join('      %d %d %d -1' % t for t in triangles)
        lines.append('''Shape {
  appearance Appearance { material Material {
    diffuseColor %.3f %.3f %.3f
    ambientIntensity 0.25
    specularColor 0.30 0.30 0.30
    shininess 0.30
  } }
  geometry IndexedFaceSet {
    solid TRUE
    creaseAngle 0.35
    coord Coordinate { point [
%s
    ] }
    coordIndex [
%s
    ]
  }
}''' % (*rgb, points, faces))
    (OUT / (NAME + '.wrl')).write_text('\n\n'.join(lines) + '\n')
    print('Generated and re-read valid STEP:', step)
    print('Envelope 2.60 x 1.30 x 0.680 mm; cathode stripe at negative X')


if __name__ == '__main__':
    main()
