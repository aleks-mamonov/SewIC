#from __future__ import annotations
import logging
from typing import Union, Dict
from abc import ABC

from ic_stitcher.layout.floorplaner import * 
from ic_stitcher.schematic.netlister import * 
from ic_stitcher.utils.Logging import addStreamHandler
#import klayout_plugin.ip_builder.schematic.netlister as netlist

from ic_stitcher.custom.connections import Pin, Net

class ICStitchError(BaseException): ...

class Item():
    def __init__(self, subcell:Union["CustomCell", "LeafCell"],
                 connections:Dict[str,Union[str,Pin,Net]],
                 trans = R0) -> None:
        if not isinstance(subcell, (CustomCell,LeafCell)):
            raise ICStitchError(f"Error: unsupported type of a subcell {subcell.__class__}, expect CustomCell or LeafCell")
        self.cell:Union[CustomCell,LeafCell] = subcell
        self.trans = trans
        self.cell_name:str = subcell.name
        self.is_instantiated = False
        self.connections:Dict[str,Net] = self._map_connections(connections)
        self.instance_name:Union[str,None] = None
        self._lay_instance:Union[CustomInstance,None] = None
        self._sch_instance:Union[CustomNetlistInstance,None] = None
        
    def _map_connections(self, connections:Dict[str,Union[str,Pin,Net]]) -> Dict[str,Net]:
        res = {}
        for term, conn in connections.items():
            net = None
            if isinstance(conn, Pin):
                net = Net(conn.full_name)
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
            res[pin.full_name] = net
        return res
    
    def _connect_layout(self, parent_lay:CustomLayoutCell):
        lay_instance = parent_lay.insert(self.instance_name, self.cell.layout, self.trans)
        for term, cell_net in self.connections.items():
            net_name = cell_net._lay_name
            if cell_net._layout is None: # Create a Layout Net
                ref_pin = lay_instance.terminals[term]
                cell_net._layout = parent_lay.add_net(net_name, ref_pin)
                if cell_net.pin:
                    pin_name = cell_net.pin._lay_name
                    cell_net.pin._layout = parent_lay.add_pin(cell_net._layout, pin_name)
            lay_instance.connect(term, cell_net._layout)
        self._lay_instance = lay_instance
        
    def _connect_netlist(self, parent_sch:CustomNetlistCell):
        sch_instance = parent_sch.insert(self.instance_name, self.cell.netlist)
        for term, cell_net in self.connections.items():
            net_name = cell_net._sch_name
            if cell_net._netlist is None: # Create a Netlist Net
                cell_net._netlist = parent_sch.add_net(net_name)
                if cell_net.pin:
                    pin_name = cell_net.pin._sch_name
                    cell_net.pin._netlist = parent_sch.add_pin(cell_net._netlist, pin_name)
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
        self.items:Dict[str, Item] = {}
        self.pins:Dict[str, Pin] = {}
        self.nets:Dict[str, Net] = {}
    
    def claim(self, outpath:str = "./", layfile:str = "", schfile = ""):
        " Save all data in outpath with default name, or in layfile/schfile if present "
        out_path = Path(outpath)
        if self.layout:
            if layfile:
                laypath = layfile
            else:
                layfile_name = f"{self.name}.gds"
                out_path.mkdir(parents=True, exist_ok=True)
                laypath = out_path/layfile_name 
            self.layout.save(laypath)
        
        if self.netlist:
            if schfile:
                schpath = schfile
            else:
                schfile_name = f"{self.name}.cdl"
                out_path.mkdir(parents=True, exist_ok=True)
                schpath = out_path/schfile_name 
            self.netlist.save(schpath)

PCELL_DECLARATION = []
class CustomCell(_BaseCell, ABC):
    
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
            except LayoutError as exc:
                raise ICStitchError(f"Failed to connect Layout.\n{exc}")
        else:
            self._logger.debug(f"Layout for {instance_name} is skiped")
        if self.netlist is not None:
            try:
                self._logger.debug(f"Connecting Netlist")
                item._connect_netlist(self.netlist)
            except NetlisterError as exc:
                raise ICStitchError(f"Failed to connect Netlist.\n{exc}")
        else:
            self._logger.debug(f"Netlist for {instance_name} is skiped")
        item.is_instantiated = True
        self._update_nets(item)
        self.items[instance_name] = item
    
    def __getitem__(self, instance_name:str):
        return self.items[instance_name]
    
    def _update_nets(self, item:Item):
        for net in item.connections.values():
            net_name = net.full_name
            if net_name in self.nets:
                raise ICStitchError(f"Net '{net_name}' is already existed in the cell")
            self.nets[net_name] = net
            if net.pin is not None:
                pin_name = net.pin.full_name
                if pin_name in self.pins:
                    raise ICStitchError(f"Pin '{pin_name}' is already existed in the cell")
                self.pins[pin_name] = net.pin
            
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
    
    def __subclasses__(self, do_pcell = False):
        if do_pcell:
            PCELL_DECLARATION.append(self)
        return super().__subclasses__()
    
class LeafCell(_BaseCell):
    _loaded:Dict[str, "LeafCell"] = {}
    def __new__(cls, cell_name, *arg, **kwargs):
        # Check if an object with the given name already exists
        if cell_name in cls._loaded:
            # Reusing existing object
            return cls._loaded[cell_name]
        
        # Create a new instance if not found
        instance = super().__new__(cls)
        cls._loaded[cell_name] = instance  # Store the instance in the dictionary
        return instance
    
    def __init__(self, cell_name, check_pins_mismatch = True):
        super().__init__(cell_name, LayLeafCell(cell_name), LeafNetlistCell(cell_name))
        self.pins = self._find_pins()
        if check_pins_mismatch:
            self._check_pins()

    def _find_pins(self):
        """ Find all pins from Layout and Netlist """
        res = {}    
        for pin_name, lay_pin in self.layout.pins.items():
            if pin_name in res:
                pin = res[pin_name]
            else:
                pin = Pin.from_text(pin_name)
                res[pin_name] = pin
            pin._layout = lay_pin    
            
        for pin_name, sch_pin in self.netlist.pins.items():
            if pin_name in res:
                pin = res[pin_name]
            else:
                pin = Pin.from_text(pin_name)
                res[pin_name] = pin
            pin._netlist = sch_pin
            
        if not res:
            LOGGER.warning(f"No PINs are found for a leafcell {self.name}")
                
        return res

    def _check_pins(self):
        """ Check all pins on matching """
        from_lay = set([n for n,p in self.pins.items() if p._layout is not None])
        from_sch = set([n for n,p in self.pins.items() if p._netlist is not None])
        all_pin_names = from_lay or from_sch
        only_lay = all_pin_names ^ from_lay
        only_sch = all_pin_names ^ from_sch
        mismatched = False
        if only_lay or only_sch:
            mismatched = True
            
        if mismatched:
            msg = f"Layout and Netlist PINs are mismatched for {self.name}\n"
            msg += f"Only in LAYOUT: {list(only_lay)}\n"
            msg += f"Only in NETLIST: {list(only_sch)}\n"
            raise ICStitchError(msg)