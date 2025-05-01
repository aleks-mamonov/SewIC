from .layout import *
from .schematic import *
#from .abstract import *

REGISTERED_TECHS = []
def register_tech(lyt_file:str):
        lyt_path = Path(lyt_file)
        if(not lyt_path.exists()):
            raise FileNotFoundError(lyt_file)
        new_tech = kdb.Technology()
        new_tech.load(lyt_file)
        REGISTERED_TECHS.append(kdb.Technology.register_technology(new_tech))
        
class GlobalConfigurations():
    pass

def _GET_LEAFCELL(name:str, pathes:list[Path]):
    for path in pathes:
        if Path(path).stem == name:
            return path
    return None