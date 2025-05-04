from typing import List, Tuple, Union
from pathlib import Path

from .global_configs import GlobalConfigs as glconf
from .global_configs import Layer, Mapper

class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_pattern)
    LEAFCELL_PATH:List[Union[Path, str]] = []
    
    # Define layers for searching pins and labels
    PIN_LAY:List[Tuple[Layer,Layer]] = []
    
    # Define a label layer for newly placed instances
    INSTANCE_LABEL_LAYER:Layer = Layer(99,99)
    
    # Print more information on Layout building
    VERBOSE:bool = glconf.VERBOSE
    
    # Input Layer Mapping Object, see https://www.klayout.de/doc-qt5/code/class_LayerMap.html 
    # to have more information on the mapping.
    # Can run from_tech(), to load layer properties from technology file
    INPUT_MAPPER:Mapper = glconf.INPUT_MAPPER
    
    # Specifies whether other layers shall be created during file reading
    CREATE_OTHER_LAYERS:bool = True
    
    
    