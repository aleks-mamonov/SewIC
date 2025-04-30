from typing import List, Tuple
from pathlib import Path

import klayout.db as kdb

PIN_SETUP = tuple[str]|tuple[int,int]|tuple[int,int,str]
class Layer(kdb.LayerInfo):
    def __str__(self):
        return self.to_s()
    def __repr__(self):
        return str(self)
    
class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_path)
    LEAFCELL_PATH:List[Path | str] = []
    
    # Define layers for searching pins and labels
    PIN_LAY:List[tuple[Layer,Layer]] = []
    
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
        kdb.Technology.register_technology(cls._tech)
        pass
    
    # Print more information on Layout building
    VERBOSE = False
    
    # Net and Pin subname delimiter
    SUBNET_DELIMITER:str = "#"
