# Local component models

`D_SOD-323HE_SS14HE.step` and `.wrl` are original, unbranded parametric
SOD-323HE representations originally dimensioned from TECH PUBLIC SS14HE.
They are retained as representative models for the selected LRC LMBR140ET1G;
the HE package has a large underside cathode termination. The `SS14HE` file
and footprint names are retained to avoid unnecessary geometry changes.

The body is 2.00 x 1.30 mm, with 2.60-mm overall terminal span and 0.680-mm
total height. Contacts are 1.65 x 0.80 mm (cathode) and 0.45 x 0.60 mm
(anode), with 0.15-mm thickness. These choices are inside the ranges on the
[manufacturer's outline drawing](https://datasheet.lcsc.com/datasheet/pdf/6c23897d9338a6092c7736bca8f498a2.pdf?productCode=C28646397).
The replacement [LRC drawing](https://www.lrc.cn/Upload/PDF/Product/SBD/LMBR140ET1G.pdf)
specifies a 1.90 x 1.25-mm nominal molding; the retained 2.00 x 1.30-mm model
is a close visual representation, not a dimensionally exact supplier model.
The body outline, polarity stripe and contacts share the footprint
origin; negative X is cathode/pad 1. Both STEP and VRML include material colors.

Mold draft, stripe size and colors are representative visual details. This
is not supplier-certified mechanical CAD and does not replace the drawing
for tolerance or assembly decisions. The existing copper lands are unchanged.

Regenerate with FreeCAD's Python and [gen_d1_model.py](../tools/gen_d1_model.py).
The script uses headless geometry APIs and does not open a GUI. STEP units
are millimetres; VRML coordinates use KiCad's 2.54-mm unit convention.

The QFN-80 models predate this diode correction and are unchanged.

`HCTL_HC-PZ127-7.2L-2x5PS.step` and `.wrl` are original, unbranded
representations of the selected bare J2 header. The base is 6.35 x 3.40 mm,
1.0 mm thick, with its top 1.50 mm above the PCB. Ten 0.40-mm square contacts
use a 1.27 x 1.27-mm mating grid and project 4.0 mm above the base; the overall
height is 5.50 mm and SMT terminal span is 5.50 mm. These dimensions follow
the [HCTL drawing](https://datasheet.lcsc.com/datasheet/pdf/6cceb9a5157e418f0d202dde8ff2fbeb.pdf?productCode=C27985146).
Lead bends, natural PA6T color and flash-gold appearance are representative,
not supplier-certified CAD. The model contains no key, shroud or branding.
Regenerate headlessly with FreeCAD's Python and
[gen_j2_model.py](../tools/gen_j2_model.py); it uses the shared STEP coloring
helper in `gen_d1_model.py`. STEP is millimetres; VRML uses KiCad's 2.54-mm unit.
