from __future__ import annotations
from dataclasses import dataclass, field
import logging
from uuid import uuid4

from .layout.floorplaner import * 
from .schematic.netlister import * 
from .utils.Logging import addStreamHandler
#import klayout_plugin.ip_builder.schematic.netlister as netlist

from .layout.global_configs import GlobalLayoutConfigs as layconfig
from .schematic.global_configs import GlobalSchematicConfigs as schconfig

class Pin():
    def __init__(self, name:str):
        self.name = name
        self._layout:PlacedPin|LayPin = None
        self._netlist:NetlistPin = None
        
    def copy(self):
        new_net = Pin(self.name)
        new_net._layout = self._layout.copy()
        new_net._netlist = self._netlist.copy()
        return new_net
        
class Net():
    def __init__(self, name:str):
        self.name = name
        self._layout:LayNet = None
        self._netlist:NetlistNet = None
        self.pin:Pin = None        
        
class NetBus(list):
    def __init__(self, name:str, stop = 0):
        self.name = name
        for i in range(stop):
            self.append(Net(f"{name}[{i}]"))

class PinBus(list):
    def __init__(self, name:str, stop = 0):
        self.name = name
        for i in range(stop):
            self.append(Pin(f"{name}[{i}]"))
        
class ICStitchError(BaseException): ...

class Item():
    def __init__(self, subcell:CustomCell | LeafCell,
                 connections:dict[str,str|Pin|Net],
                 trans = R0) -> None:
        if not isinstance(subcell, (CustomCell,LeafCell)):
            raise ICStitchError(f"Error: unsupported type of a subcell {subcell.__class__}, expect CustomCell or LeafCell")
        self.cell = subcell
        self.trans = trans
        self.cell_name = subcell.name
        self.is_instantiated = False
        self.connections = self._map_connections(connections)
        self.instance_name = None
        self._lay_instance = None
        self._sch_instance = None
        
    def _map_connections(self, connections:dict[str,str|Pin|Net]) -> dict[str,Net]:
        res = {}
        for term, conn in connections.items():
            net = None
            if isinstance(conn, Pin):
                net = Net(conn.name)
                net.pin = conn
            elif isinstance(conn, Net):
                net = conn
            elif isinstance(conn, str):
                net = Net(conn)
            else:
                msg = f"Unexpected type of the contact must be Pin, Net or str, given {type(conn)}"
                raise ICStitchError(msg)
            pin = self.cell.pins.get(term)
            if pin is None:
                raise ICStitchError(f"PIN '{term}' is not in the cell '{self.cell_name}'")
            res[pin.name] = net
        return res
    
    def _connect_layout(self, parent_lay:CustomLayoutCell):
        lay_instance = parent_lay.insert(self.instance_name, self.cell.layout, self.trans)
        for term, cell_net in self.connections.items():
            net_name = cell_net.name
            if cell_net._layout is None: # Create a Layout Net
                ref_pin = lay_instance.terminals[term]
                cell_net._layout = parent_lay.add_net(net_name, ref_pin)
                if cell_net.pin:
                    cell_net.pin._layout = parent_lay.add_pin(cell_net._layout)
            lay_instance.connect(term, cell_net._layout)
        self._lay_instance = lay_instance
        
    def _connect_netlist(self, parent_sch:CustomNetlistCell):
        sch_instance = parent_sch.insert(self.instance_name, self.cell.netlist)
        for term, cell_net in self.connections.items():
            net_name = cell_net.name
            if cell_net._netlist is None: # Create a Netlist Net
                cell_net._netlist = parent_sch.add_net(net_name)
                if cell_net.pin:
                    cell_net.pin._netlist = parent_sch.add_pin(cell_net._netlist)
            sch_instance.connect(term, cell_net._netlist)
        self._sch_instance = sch_instance
    
    def __str__(self):
        return f"{self.instance_name} ({self.cell_name}) {self.connections}"

class _BaseCell():
    def __init__(self, cell_name:str, layout: CustomLayoutCell, netlist: CustomNetlistCell):
        self.name = cell_name
        self.layout = layout
        self.netlist = netlist
        self._logger = logging.getLogger(cell_name)
        addStreamHandler(self._logger, verbose=True)
        self._logger.setLevel(logging.DEBUG)
        self._logger.debug(f"Cell: {cell_name}")
        self.items:dict[str, Item] = {}
        self.pins:dict[str, Pin] = {}
        self.nets:dict[str, Net] = {}
    
    def claim(self, laypath:str = "", schpath = ""):
        laypath = laypath or f"./{self.name}.gds"
        self.layout.layout.write(laypath)
        schpath = schpath or f"./{self.name}.cdl"
        self.netlist.save_netlist(schpath)

class CustomCell(_BaseCell):
    def __init__(self, cell_name:str) -> None:
        super().__init__(cell_name, CustomLayoutCell(cell_name), CustomNetlistCell(cell_name))
                
    def __setitem__(self, instance_name:str, item:Item):
        if(type(item) is not Item):
            raise ICStitchError("Item must be an object of Item class")
        if(instance_name in self.items.keys()):
            raise ICStitchError(f"Item {instance_name} must have an unique name")
        if item.is_instantiated:
            raise ICStitchError(f"Item {instance_name} is already instantiated")
        item.instance_name = instance_name
        self._logger.info(f"{item}")
        if self.layout is not None:
            try:
                self._logger.debug(f"Connecting Layout")
                item._connect_layout(self.layout)
            except CompilerLayoutError as exc:
                raise ICStitchError(f"Failed to connect Layout.\n{exc}")
        if self.netlist is not None:
            try:
                self._logger.debug(f"Connecting Netlist")
                item._connect_netlist(self.netlist)
            except NetlisterError as exc:
                raise ICStitchError(f"Failed to connect Netlist.\n{exc}")
        item.is_instantiated = True
        self.items[instance_name] = item
    
    def __getitem__(self, instance_name:str):
        return self.items[instance_name]

    def find_pin(self, name:str):
        if(not isinstance(name, str)):
            raise ICStitchError("Incorrect type of the name, must be 'str'")
        pin = Pin(name)
        return pin
    
    def find_net(self, name:str):
        if(not isinstance(name, str)):
            raise ICStitchError("Incorrect type of the name, must be 'str'")
        net = Net(name, pin=True)
        return net
    
class LeafCell(_BaseCell):
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
        super().__init__(cell_name, LayLeafCell(cell_name), LeafNetlistCell(cell_name))
        self.pins = self._find_pins()

    def _find_pins(self):
        """ Find and check all pins from Layout/Netlist """
        pin_names: list[str] = []
        if self.layout:
            pin_names = sorted(list(self.layout.pins.keys()))
            
        if self.netlist:
            sch_pins = sorted(list(self.netlist.pins.keys()))
            if pin_names:
                if pin_names != sch_pins:
                    raise ICStitchError(f"PIN mismatch L: {pin_names} <-> N: {sch_pins}")
            else:
                pin_names = sch_pins
        res = {}    
        for pin_name in pin_names:
            pin = Pin(pin_name)
            pin._layout = self.layout.pins[pin_name]
            pin._netlist = self.netlist.pins[pin_name]
            res[pin_name] = pin
        return res
