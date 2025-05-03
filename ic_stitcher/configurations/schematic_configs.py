from typing import List, Tuple, Union
from pathlib import Path

from .global_configs import GlobalConfigs as glconf

class GlobalSchematicConfigs():
    # Define the list of pathes to layout leafcells
    # Better use glob from pathlib.Path
    LEAFCELL_PATH:List[Union[Path,str]] = []
    
    # Name of primitive devices, existing as a subcircuits
    NETLIST_PRIMITIVES:List[str] = []

    # Indicating whether to use net names (true) or net numbers (false).
    SAVE_USE_NET_NAMES:bool = True

    # Indicating whether to embed comments for position etc. (true) or not (false).
    SAVE_WITH_COMMENTS:bool = False
    
    # Print more information on Layout building
    VERBOSE = glconf.VERBOSE
    