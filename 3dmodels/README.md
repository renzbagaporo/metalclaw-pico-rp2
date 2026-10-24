# Local component models

`D_SOD-323HE_SS14HE.step` and `.wrl` are original, unbranded parametric
representations of TECH PUBLIC SS14HE. They replace the unsuitable generic
SOD-323 model; the HE package has a large underside cathode termination.

The body is 2.00 x 1.30 mm, with 2.60-mm overall terminal span and 0.680-mm
total height. Contacts are 1.65 x 0.80 mm (cathode) and 0.45 x 0.60 mm
(anode), with 0.15-mm thickness. These choices are inside the ranges on the
[manufacturer's outline drawing](https://datasheet.lcsc.com/datasheet/pdf/6c23897d9338a6092c7736bca8f498a2.pdf?productCode=C28646397).
The nominal body outline, polarity stripe and contacts share the footprint
origin; negative X is cathode/pad 1. Both STEP and VRML include material colors.

Mold draft, stripe size and colors are representative visual details. This
is not supplier-certified mechanical CAD and does not replace the drawing
for tolerance or assembly decisions. The existing copper lands are unchanged.

Regenerate with FreeCAD's Python and [gen_d1_model.py](../tools/gen_d1_model.py).
The script uses headless geometry APIs and does not open a GUI. STEP units
are millimetres; VRML coordinates use KiCad's 2.54-mm unit convention.

The QFN-80 models predate this diode correction and are unchanged.
