from typing import List, Tuple
from pathlib import Path

import klayout.db as kdb

PIN_SETUP = tuple[str]|tuple[int,int]|tuple[int,int,str]
class Layer():
    def __init__(self, *args) -> None:
        self.info = kdb.LayerInfo(*args)
    def __str__(self):
        return self.info.to_s()
    def __repr__(self):
        return str(self)
    
class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_path)
    LEAFCELL_PATH:List[Path | str] = []
    
    # Define layers for searching pins and labels
    _PIN_LAY:List[tuple[Layer,Layer]] = []
    
    @classmethod
    def PIN_SETUPS(self,pin_setups:list[tuple[PIN_SETUP,PIN_SETUP]]):
        try:
            iter(pin_setups)
        except TypeError as exc:
            raise TypeError(f"Invalid type of pin setups: {exc}")
        for setup in pin_setups:
            if(not isinstance(setup, tuple)):
                raise TypeError(f"PIN setup must be a tuple")
            pin_layer = None
            pin_setup = setup[0]
            if(isinstance(pin_setup, str)):
                pin_layer = Layer(pin_setup)
            else:
                pin_layer = Layer(*pin_setup)
            label_layer = None
            label_setup = setup[1]
            if(isinstance(label_setup, str)):
                label_layer = Layer(label_setup)
            else:
                label_layer = Layer(*label_setup)

            self._PIN_LAY.append((pin_layer, label_layer))

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
