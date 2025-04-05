from __future__ import annotations
import klayout.db as pya_db
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, ClassVar
import functools

from .layout import * 
#import klayout_plugin.ip_builder.schematic.netlister as netlist

@dataclass(frozen=True)
class Pin():
    name:str

@dataclass(frozen=True)
class Net():
    name:str
        
class _Pin():
    def __init__(self, pin:Pin):
        self.name = pin.name
        self._lay = None
        self._sch = None

class _Net():
    def __init__(self, net:Net):
        self.name = net.name
        self._lay = None
        self._sch = None

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
        self.pins = {}
        self.nets = {}
        #self.schematic = netlist.CustomNetlist(cell_name)
        #self.declare(*pars, **kwpars)
    
    def __setitem__(self, instance_name:str, item:Item):
        if(type(item) is not Item):
            raise IPlantError("Item must be an object of Item class")
        if(instance_name in self.items.keys()):
            raise IPlantError(f"Item {instance_name} must have an unique name")
        self._connect_lay_inst(instance_name, item)
        self.items[instance_name] = item

    def _connect_lay_inst(self, name:str, item:Item):
        lay_instance = self.layout.insert(item.cell.layout, name, item.trans)
        lay_connect:dict[str,LayNet] = {}
        for term, conn in item.connections.items():
            if(isinstance(conn, Pin)):
                inst_pin = lay_instance.terminals[term]
                lay_pin = self.layout.add_pin(inst_pin, conn.name)
                cell_pin = _Pin(conn)
                cell_pin._lay = lay_pin
                self.pins[lay_pin.name] = lay_pin
                lay_net = self.layout.nets[conn.name]
                froz_net = Net(lay_net.name)
                cell_net = _Net(froz_net)
                cell_net._lay = lay_net
                self.nets[lay_net.name] = cell_net
                lay_connect[term] = lay_net
            else:
                lay_net = self.layout.add_net(conn)
                froz_net = Net(lay_net.name)
                cell_net = _Net(froz_net)
                cell_net._lay = lay_net
                self.nets[lay_net.name] = cell_net
                lay_connect[term] = lay_net
        lay_instance.connect(lay_connect)
        item.lay_instance = lay_instance

    def __getitem__(self, instance_name:str):
        return self.items[instance_name]
    
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
