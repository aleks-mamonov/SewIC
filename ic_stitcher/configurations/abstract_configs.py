from typing import List, Tuple
from pathlib import Path

import klayout.db as kdb
from .layout_configs import Layer, Mapper

class GlobalAbstractConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_pattern)
    LEAFCELL_PATH:List[Path | str] = []
    
    # Define layers for searching pins and labels
    PIN_LAY:List[tuple[Layer,Layer]] = []
    
    # Define a lable layer for newly placed instances
    INSTANCE_LABLE_LAYER:Layer = None

    # Specify Technology name, it must be registered before with "register_tech"
    # Technology name can also be used to find valid layer names, see Mapper.from_tech()
    TECH_NAME = ""
    
    # Print more information on Layout building
    VERBOSE = False
    
    # Net and Pin subname delimiter
    SUBNET_DELIMITER:str = "#"
    
    # Input Layer Mapping Object, see https://www.klayout.de/doc-qt5/code/class_LayerMap.html 
    # to have more information on the mapping.
    # Can run from_tech(), to load layer properties from technology file
    INPUT_MAPPER = Mapper()
    
    # Specifies whether other layers shall be created during file reading
    CREATE_OTHER_LAYERS = True
