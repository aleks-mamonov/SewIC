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
        
class _CellPin():
    def __init__(self, name:str):
        self.name:str = name
        self._lay:PlacedPin = None
        #self._sch_name:str = name
        # if(pin.name.find("#") != -1):
        #     self._sch_name = pin.name.split("#")[0]

class _CellNet():
    def __init__(self, name:str):
        self.name:str = name
        self.lnet:LayNet = None
        self.pin:_CellPin = None
        #self._sch_name:str = net.name
        # if(pin.name.find("#") != -1):
        #     self._sch_name = net.name.split("#")[0]
        #self._sch:str = None
    
    def add_lay(self, net:LayNet):
        self.lnet = net
        if net.top_pin:
            lpin = net.top_pin
            self.pin = _CellPin(self.name)
            self.pin._lay = lpin

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

    def find_pin(self, name:str):
        if(not isinstance(name, str)):
            raise IPlantError("Incorrect type of the name, must be 'str'")
        pin = Pin(name)
        return pin
    
    def find_net(self, name:str):
        if(not isinstance(name, str)):
            raise IPlantError("Incorrect type of the name, must be 'str'")
        net = Net(name, pin=True)
        return net
    
    def get_net(self, name:str):
        if name in self.nets:
            return self.nets[name]
        net = _CellNet(name)
        self.nets[name] = net
        return net
    
    def add_pin(self, net:_CellNet):
        name = net.name
        if name in self.pins:
            raise IPlantError(f"Pin '{name}' is already existed")
        pin = self.layout.add_pin(net.lnet)
        net.pin = pin
        self.pins[name] = pin
        return pin

    def _connect_lay_inst(self, name:str, item:Item):
        lay_instance = self.layout.insert(item.cell.layout, name, item.trans)
        lay_connect:dict[str,LayNet] = {}
        for term, conn in item.connections.items():
            name = conn
            if(isinstance(conn, Pin) or isinstance(conn, Net)):
                name = conn.name
            else:
                msg = f"Unexpected type of the contact must be Pin or str, given {type(conn)}"
                raise IPlantError(msg)
            cell_net = self.get_net(name)
            ref_pin = lay_instance.terminals[term]
            lnet = self.layout.add_net(conn.name, ref_pin)
            if(isinstance(conn, Pin)):
                lpin = self.layout.add_pin(lnet)
            cell_net.add_lay(lnet)
            lay_connect[term] = lnet
        lay_instance.connect(lay_connect)
        item.lay_instance = lay_instance

    def __getitem__(self, instance_name:str):
        return self.items[instance_name]
    
    def claim(self, path:str):
        self.layout.layout.write(path)


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
