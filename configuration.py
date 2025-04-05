from pathlib import Path
#from .ip_builder.layout import GlobalLayoutConfigs as layconf
from .ic_stitcher.configurations import GlobalLayoutConfigs as layconf
# from .ip_builder.schematic import GlobalSchematicConfigs as schconf
from .ic_stitcher.configurations import GlobalSchematicConfigs as schconf

LEAFCELL_PATH = "/home/aleksandr/.klayout/python/klayout_plugin/leafcells"

# Layout Configurations
layconf.LEAFCELL_PATH = Path(LEAFCELL_PATH).glob("**/*.gds")

layconf.register_tech("/home/aleksandr/.klayout/salt/sky130A_el/sky130A.lyt")
layconf.TECH_NAME = "sky130A_el"
layconf.PIN_SETUPS([
    ( (68, 16), (68, 5) ) # Metal1
])

# layconf.PIN_SETUPS([
#     ( "met1.pin", "met1.label") # Metal1
# ])

# Schematic Configurations
schconf.LEAFCELL_PATH = Path(LEAFCELL_PATH).glob("**/*.cir")

schconf.NETLIST_PRIMITIVES = []