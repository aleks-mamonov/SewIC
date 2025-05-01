from typing import List, Tuple
from pathlib import Path

import klayout.db as kdb
import xml.etree.ElementTree as ET


class Layer(kdb.LayerInfo):
    def __str__(self):
        return self.to_s()
    def __repr__(self):
        return str(self)
    
    @classmethod
    def from_prop(cls, s:str):
        name, code = s.split(" ", maxsplit=1)
        code = code.removeprefix("(")
        layer, data = code.removesuffix(")").split("/", maxsplit=1)
        info = cls(int(layer), int(data), name)
        return info
   
class Mapper(kdb.LayerMap):
    def from_tech(self):
        tech = kdb.Technology.technology_by_name(GlobalLayoutConfigs.TECH_NAME)
        if not tech:
            raise ValueError(f"Technology {GlobalLayoutConfigs.TECH_NAME} is not registered, use register_tech first")
        tree = ET.parse(tech.eff_layer_properties_file())
        properties = tree.getroot()
        for ind, prop in enumerate(properties):
            if prop.tag == "properties":
                fullname = prop.find("name").text
                full = Layer.from_prop(fullname)
                inp = Layer(full.layer, full.datatype)
                self.map(inp, ind)
 
class GlobalLayoutConfigs():
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
    
    
    