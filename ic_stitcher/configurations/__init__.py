from .layout_configs import *
from .schematic_configs import *
#from .abstract import *
from .global_configs import *
from .global_configs import _IS_KLAYOUT

from typing import List

REGISTERED_TECHS = []
def register_tech(lyt_file:str):
    if _IS_KLAYOUT: # In Klayout technologies are registered
        return None
    lyt_path = Path(lyt_file)
    if(not lyt_path.exists()):
        raise FileNotFoundError(lyt_file)
    new_tech = kdb.Technology()
    new_tech.load(lyt_file)
    REGISTERED_TECHS.append(kdb.Technology.register_technology(new_tech))
        
def _GET_LEAFCELL(name:str, pathes:List[Path]):
    for path in pathes:
        if Path(path).stem == name:
            return path
    return None