from pathlib import Path
from ic_stitcher.configurations import GlobalLayoutConfigs as layconf
from ic_stitcher.configurations import GlobalConfigs as globalconf
from ic_stitcher.configurations import GlobalSchematicConfigs as schconf
from ic_stitcher.configurations import Layer, register_tech
LEAFCELL_PATH = "./leafcells"

# Layout Configurations
layconf.LEAFCELL_PATH = Path(LEAFCELL_PATH).glob("**/*.gds")

register_tech("/home/aleksandr/.klayout/salt/gf180mcu/tech/gf180mcu.lyt")
globalconf.TECH_NAME = "gf180mcu"
layconf.PIN_LAY = [
    (Layer(30, 0), Layer(30, 10)), # Poly2
    (Layer(34, 0), Layer(34, 10)), # Metal1
    (Layer(36, 0), Layer(36, 10)), # Metal2
    (Layer(42, 0), Layer(42, 10)), # Metal3
]

# Schematic Configurations
schconf.LEAFCELL_PATH = Path(LEAFCELL_PATH).glob("**/*.sp")

schconf.NETLIST_PRIMITIVES = ["nfet_06v0", "pfet_06v0"]