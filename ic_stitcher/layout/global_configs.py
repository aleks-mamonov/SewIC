from typing import List, Tuple, Union
from pathlib import Path

try:
    import klayout.db as kdb
except ModuleNotFoundError as e:
    import pya as kdb

class Layer(kdb.LayerInfo):
    def __str__(self:kdb.LayerInfo):
        return self.to_s()
    def __repr__(self:kdb.LayerInfo):
        return str(self)
    
class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_path)
    LEAFCELL_PATH:List[Union[Path, str]] = []
    
    # Define layers for searching pins and labels
    PIN_LAY:List[Tuple[Layer,Layer]] = []
    
    # Define a lable layer for newly placed instances
    INSTANCE_LABLE_LAYER:Layer = None
    
    # KLayout layout object, used for inside-KLayout run
    KLAYOUT = None 

    TECH_NAME = ""

    _tech = kdb.Technology()
    @classmethod
    def register_tech(cls, lyt_file:str):
        lyt_path = Path(lyt_file)
        if(not lyt_path.exists()):
            raise FileNotFoundError(lyt_file)
        cls._tech.load(lyt_file)
        cls._tech.add_other_layers = False
        kdb.Technology.register_technology(cls._tech)
        pass
    
    # Print more information on Layout building
    VERBOSE = False
    
    # Net and Pin subname delimiter
    SUBNET_DELIMITER:str = "#"
