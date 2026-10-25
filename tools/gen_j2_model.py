#!/usr/bin/env python3
"""Generate an unbranded HCTL HC-PZ127-7.2L-2x5PS header model headlessly.

Dimensions from the selected supplier drawing: 6.35 x 3.40 mm base,
1.0-mm molding thickness, 1.50-mm base top above PCB, 4.0-mm mating posts,
1.27 x 1.27-mm contact grid, 0.40-mm square contacts, 5.50-mm SMT tip span.
The L-shaped lead bends, molding color and gold finish are representative.
No branding, key or molded pin-1 feature is invented.

Run with FreeCAD's bundled Python as documented in 3dmodels/README.md.
"""
from pathlib import Path
import sys

FREECAD_LIB = Path('/Applications/FreeCAD.app/Contents/Resources/lib')
if FREECAD_LIB.is_dir():
    sys.path.insert(0, str(FREECAD_LIB))
import FreeCAD as App
import Part
from gen_d1_model import color_step

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / '3dmodels'
NAME = 'HCTL_HC-PZ127-7.2L-2x5PS'


def main():
    OUT.mkdir(exist_ok=True)
    body = Part.makeBox(3.40, 6.35, 1.00, App.Vector(-1.70, -3.175, 0.50))
    contacts = []
    for y in (-2.54, -1.27, 0.0, 1.27, 2.54):
        for x in (-0.635, 0.635):
            stem = Part.makeBox(0.40, 0.40, 5.30,
                                App.Vector(x - 0.20, y - 0.20, 0.20))
            toe_x = -2.75 if x < 0 else x - 0.20
            toe = Part.makeBox(2.315, 0.40, 0.40,
                               App.Vector(toe_x, y - 0.20, 0.0))
            contact = stem.fuse(toe).removeSplitter()
            assert contact.isValid() and len(contact.Solids) == 1
            contacts.append(contact)
            body = body.cut(stem)
    shapes = [body] + contacts
    # Natural PA6T and flash-gold contacts; appearance is representative.
    colors = [(0.88, 0.86, 0.78)] + [(0.83, 0.65, 0.25)] * len(contacts)
    for shape in shapes:
        assert shape.isValid() and shape.Volume > 0
    whole = Part.makeCompound(shapes)
    for value, expected in ((whole.BoundBox.XLength, 5.50),
                            (whole.BoundBox.YLength, 6.35),
                            (whole.BoundBox.ZLength, 5.50)):
        assert abs(value - expected) < 1e-7
    step = OUT / (NAME + '.step')
    whole.exportStep(str(step))
    color_step(step, colors)
    restored = Part.read(str(step))
    assert restored.isValid() and len(restored.Solids) == 11
    assert abs(restored.BoundBox.ZLength - 5.50) < 1e-6
    lines = ['#VRML V2.0 utf8',
             '# Original unbranded 2x5 HCTL header representation.',
             '# Dimensions in mm / 2.54 for KiCad VRML; 4.0-mm mating posts.']
    for shape, rgb in zip(shapes, colors):
        vertices, triangles = shape.tessellate(0.01)
        points = ',\n'.join('      %.9f %.9f %.9f' %
                            (v.x / 2.54, v.y / 2.54, v.z / 2.54) for v in vertices)
        faces = ',\n'.join('      %d %d %d -1' % t for t in triangles)
        lines.append('''Shape {
  appearance Appearance { material Material {
    diffuseColor %.3f %.3f %.3f
    ambientIntensity 0.25
    specularColor 0.35 0.35 0.35
    shininess 0.35
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
    print('Envelope 5.50 x 6.35 x 5.50 mm; 4.0-mm mating posts above 1.5-mm base')


if __name__ == '__main__':
    main()
