from __future__ import annotations
import klayout.db as pya_db
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict
import functools

from .layout import * 
#import klayout_plugin.ip_builder.schematic.netlister as netlist

@dataclass(frozen=True)
class Pin():
    name:str

class IPlantError(BaseException): ...

class Item():
    def __init__(self, subcell:CustomCell | LeafCell,
                 Connections:dict[str,str|Pin],
                 trans = R0) -> None:
        if(not isinstance(subcell, CustomCell)):
            raise IPlantError(f"Error: no other types is supported, except Cell and str for an Item")
        self.cell = subcell
        self.trans = trans
        self.cell_name = subcell.name
        self.is_pined = False
        self.connections = Connections
        self.lay_instance = None
        self.sch_instance = None

class CustomCell():
    def __init__(self, cell_name:str) -> None:
        self.name = cell_name
        self.items = {}
        self.layout = CustomLayoutCell(cell_name)
        #self.schematic = netlist.CustomNetlist(cell_name)
        #self.declare(*pars, **kwpars)
    
    def __setitem__(self, instance_name:str, item:Item):
        if(type(item) is not Item):
            raise IPlantError("Item must be an object of Item class")
        if(instance_name in self.items.keys()):
            raise IPlantError(f"Item {instance_name} must have an unique name")
        lay_instance = self.layout.insert(item.cell.layout, instance_name, item.trans)
        for term, conn in item.connections.items():
            if(isinstance(conn, Pin)):
                self.layout.connect_to_pin(lay_instance, term, conn.name)
            else:
                self.layout.connect_to_net(lay_instance, term, conn)

        item.lay_instance = lay_instance
        self.items[instance_name] = item

    def __getitem__(self, instance_name:str):
        return self.items[instance_name]

    def state_pin(self, net_name:str):
        self.layout.attach_pin(net_name)

    def claim(self, path:str):
        self.layout.layout.write(path)
    
    def get_pin(self, pin_name:str): # ??
        pass

    def create_net(self, net_name:str): # ??
        pass

class LeafCell(CustomCell):
    _loaded:dict[str, LeafCell] = {}
    def __new__(cls, cell_name, *args, **kwargs):
        # Check if an object with the given name already exists
        if cell_name in cls._loaded:
            # Reusing existing object
            return cls._loaded[cell_name]
        
        # Create a new instance if not found
        instance = super().__new__(cls)
        cls._loaded[cell_name] = instance  # Store the instance in the dictionary
        return instance
    
    def __init__(self, cell_name):
        super().__init__(cell_name)
        self.layout = LayLeafCell(cell_name)

class cell():
    def __call__(self, func):
        def wrapper(self_cell, *pins, **kwargs):
            func(*pins, **kwargs)
        return wrapper
class _Substitute():
    def __setitem__(self, instance_name:str, item:Item):
        if(type(item) is not Item):
            raise IPlantError("Item must be an object of Item class")
        if(instance_name in self.items.keys()):
            raise IPlantError(f"Item {instance_name} must have an unique name")
        lay_instance = self.layout.insert(item.cell.layout, item.trans, item.connections)
        item.lay_instance = lay_instance
                
        self.items[instance_name] = item

    def __getitem__(self, instance_name:str):
        return self.items[instance_name]

def pins(*pin_names: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self:CustomCell, *args, **kwargs):
            result = func(self, *args, **kwargs)
            for pin in pin_names:
                self.state_pin(pin)
            return result
        return wrapper
    return decorator
