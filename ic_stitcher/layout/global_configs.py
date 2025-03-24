from typing import List, Tuple
from pathlib import Path

class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells
    LEAFCELL_PATH:List[Path | str] = []
    
    # Define layer numbers for searching pins and lables
    PIN_LAY:List[Tuple[Tuple[int,int],Tuple[int,int]]] = []

    # KLayout layout object, used for inside-KLayout run
    KLAYOUT = None

    @property
    def LEAFCELL_PATH(self):
        return self.LEAFCELL_PATH
    
    @LEAFCELL_PATH.setter
    def LEAFCELL_PATH(self, value:list[Path]):
        res_dict = {}
        for netlist_path in value:
            res_dict[netlist_path.stem] = netlist_path
        self.leafcell_select = res_dict

