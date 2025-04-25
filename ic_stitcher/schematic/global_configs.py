from typing import List, Tuple
from pathlib import Path

class GlobalSchematicConfigs():
    # Define the list of pathes to layout leafcells
    # Better use glob from pathlib.Path
    LEAFCELL_PATH:List[Path | str] = []
    
    # Name of primitive devices, existing as a subcircuits
    NETLIST_PRIMITIVES:List[str] = []

    # 
    USE_NET_NAMES:bool = True

    #
    WITH_COMMENTS:bool = False
    
    # Net subname delimiter
    SUBNET_DELIMITER:str = None