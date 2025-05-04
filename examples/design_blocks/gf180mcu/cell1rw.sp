* NGSPICE file created from cell1rw.ext - technology: gf180mcuC

.subckt cell1rw BL_TOP BL_BOTTOM BR_TOP BR_BOTTOM GND_LEFT GND_RIGHT VDD_LEFT VDD_RIGHT WL_LEFT WL_RIGHT
* These signals are meant to connect on the next levels, they exist to match layout:
* BL_TOP, BL_BOTTOM
* BR_TOP, BR_BOTTOM
* GND_LEFT, GND_RIGHT
* VDD_LEFT, VDD_RIGHT
* WL_LEFT, WL_RIGHT
X0 GND a_63_149# a_18_103# GND_LEFT nfet_06v0 ad=0.627p pd=3.74u as=0.7275p ps=4.76u w=0.95u l=0.6u
X1 a_18_103# WL_LEFT BL_TOP GND_LEFT nfet_06v0 ad=0p pd=0u as=0.282p ps=2.14u w=0.6u l=0.77u
X2 a_63_149# a_18_103# VDD VDD_LEFT pfet_06v0 ad=0.27p pd=2.1u as=0.489p ps=3.38u w=0.6u l=0.6u
X3 a_63_149# WL_LEFT BR_TOP GND_LEFT nfet_06v0 ad=0.7275p pd=4.76u as=0.282p ps=2.14u w=0.6u l=0.77u
X4 VDD a_63_149# a_18_103# VDD_LEFT pfet_06v0 ad=0p pd=0u as=0.27p ps=2.1u w=0.6u l=0.6u
X5 a_63_149# a_18_103# GND GND_LEFT nfet_06v0 ad=0p pd=0u as=0p ps=0u w=0.95u l=0.6u
.ends

