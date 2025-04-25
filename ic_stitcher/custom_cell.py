from __future__ import annotations
from dataclasses import dataclass
import logging

from .layout.floorplaner import * 
from .schematic.netlister import * 
from .utils.Logging import addStreamHandler
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
        self._sch:NetlistPin = None
        #self._sch_name:str = name
        # if(pin.name.find("#") != -1):
        #     self._sch_name = pin.name.split("#")[0]

class _CellNet():
    def __init__(self, name:str):
        self.name:str = name
        self.lnet:LayNet = None
        self.pin:_CellPin = None
        self.snet:NetlistPin = None
        #self._sch_name:str = net.name
        # if(pin.name.find("#") != -1):
        #     self._sch_name = net.name.split("#")[0]
        #self._sch:str = None
    
    def add_lay(self, net:LayNet):
        self.lnet = net
            
    def add_sch(self, net:NetlistNet):
        self.lnet = net

class IPlantError(BaseException): ...

class Item():
    def __init__(self, subcell:CustomCell | LeafCell,
                 Connections:dict[str,str|Pin|Net],
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
    
    def __str__(self):
        return f"ITEM: {self.cell_name} ({self.connections})"

class CustomCell():
    def __init__(self, cell_name:str) -> None:
        self.name = cell_name
        self.layout = CustomLayoutCell(cell_name)
        self.schema = CustomNetlistCell(cell_name)
        self._logger = logging.getLogger(cell_name)
        self._logger.setLevel(logging.DEBUG)
        addStreamHandler(self._logger)
        self._logger.info(f"Cell: {cell_name}")
        #self.schematic = netlist.CustomNetlist(cell_name)
        #self.declare(*pars, **kwpars)
        self.items = {}
        self.pins = {}
        self.nets = {}
    
    def __setitem__(self, instance_name:str, item:Item):
        if(type(item) is not Item):
            raise IPlantError("Item must be an object of Item class")
        if(instance_name in self.items.keys()):
            raise IPlantError(f"Item {instance_name} must have an unique name")
        self._connect_inst(instance_name, item)
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
    
    def get_net(self, name:str) -> _CellNet:
        if name in self.nets:
            return self.nets[name]
        return None
    
    def create_net(self, name:str):
        if name in self.nets:
            raise IPlantError(f"Net '{name}' is already existed")
        net = _CellNet(name)
        self.nets[name] = net
        return net
        
    def add_pin(self, net:_CellNet):
        name = net.name
        if name in self.pins:
            raise IPlantError(f"Pin '{name}' is already existed")
        pin = _CellPin(name)
        pin._lay = self.layout.add_pin(net.lnet)
        pin._sch = self.schema.add_pin(net.snet)
        net.pin = pin
        self.pins[name] = pin
        #return pin

    def _connect_inst(self, name:str, item:Item):
        self._logger.debug(str(item))
        lay_instance = self.layout.insert(item.cell.layout, name, item.trans)
        lay_connect:dict[str,LayNet] = {}
        sch_instance = self.schema.insert(name, item.cell.schema)
        sch_connect:dict[str,NetlistPin] = {}
        for term, conn in item.connections.items():
            net_name = None
            if(isinstance(conn, Pin) or isinstance(conn, Net)):
                net_name = conn.name
            elif isinstance(conn, str):
                net_name = conn
            else:
                msg = f"Unexpected type of the contact must be Pin or str, given {type(conn)}"
                raise IPlantError(msg)
            cell_net = self.get_net(net_name)
            if cell_net is None:
                cell_net = self.create_net(net_name)
                ref_pin = lay_instance.terminals[term]
                cell_net.lnet = self.layout.add_net(net_name, ref_pin)
                cell_net.snet = self.schema.add_net(net_name)
                if(isinstance(conn, Pin)):
                    self.add_pin(cell_net)
            lay_connect[term] = cell_net.lnet
            sch_connect[term] = cell_net.snet
        lay_instance.connect(lay_connect)
        item.lay_instance = lay_instance
        sch_instance.connect(sch_connect)
        item.sch_instance = sch_instance

    def __getitem__(self, instance_name:str):
        return self.items[instance_name]
    
    def claim(self, laypath:str = "", schpath = ""):
        laypath = laypath or f"./{self.name}.gds"
        self.layout.layout.write(laypath)
        schpath = schpath or f"./{self.name}.cdl"
        self.schema.save_netlist(schpath)

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
        self.schema = LeafNetlistCell(cell_name)

