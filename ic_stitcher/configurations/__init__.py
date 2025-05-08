from .layout_configs import *
from .schematic_configs import *
#from .abstract import *
from .global_configs import *
from .global_configs import _IS_KLAYOUT

from typing import List

def register_tech(lyt_file:str):
    lyt_path = Path(lyt_file)
    tech_name = lyt_path.stem
    if(not lyt_path.exists()):
        raise FileNotFoundError(lyt_file)
    if kdb.Technology.technology_by_name(tech_name):
        return None
    new_tech = kdb.Technology()
    new_tech.load(lyt_file)
    kdb.Technology.register_technology(new_tech)
        
def _GET_LEAFCELL(name:str, pathes:List[Path]):
    for path in pathes:
        if Path(path).stem == name:
            return path
    return None