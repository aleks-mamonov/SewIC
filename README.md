# IC-Stitcher

IC-Stitcher is a Python module for building various type of integrated circuit design files (models) out of subblocks (leafcells), such as:

* Layout (GDS)
* Schematic/Netlist (Spice)
* Abstract (LEF) -> TBD

The tool is based on Klayout library, and uses Layout and Netlist modules from it. ALso facilitates the automated PCell declorations in Klayout.

## Simple Example

This example shows how to place two blocks using Net conncetions.
`

`

To achieve this PINs/PORTs description are used, so in Layout and Abstract blocks are placed to each other by PINs (defiened by d) location:

SOME PICTURE

