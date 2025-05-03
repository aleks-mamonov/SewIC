from typing import TypeVar, Union, Dict, List, Type, Generic
from ic_stitcher.configurations import GlobalConfigs as globconf
from ic_stitcher.configurations import remove_suffix

from ic_stitcher.layout.floorplaner import * 
from ic_stitcher.schematic.netlister import * 

LAY_CONN = TypeVar("CONN")
SCH_CONN = TypeVar("SCH_CONN")
class ConnectionBit(Generic[LAY_CONN, SCH_CONN]):
    def __init__(self, name:str, 
                 suffix:Union[str,int] = None,
                 index:int = None,
                 full_name_layout = True,
                 full_name_netlist = True):
        suffixed = ""
        self.delimiter = globconf.SUBNET_DELIMITER
        if suffix is not None and suffix != "":
            suffixed = f"{self.delimiter}{suffix}"
        bus_l = globconf.BUS_BRACKETS[0]
        bus_r = globconf.BUS_BRACKETS[1]
        indexed = ""
        if index is not None and index != "":
            indexed = f"{bus_l}{index}{bus_r}"
        no_suffix = name+indexed
        self.full_name = name+suffixed+indexed
        self._lay_name:LAY_CONN = self.full_name if full_name_layout else no_suffix
        self._layout:LAY_CONN = None
        self._sch_name:SCH_CONN = self.full_name if full_name_netlist else no_suffix
        self._netlist:SCH_CONN = None
        
    def __repr__(self):
        return str(self)
    
    @classmethod
    def from_text(cls, full_name:str) -> "ConnectionBit":
        bus_l = globconf.BUS_BRACKETS[0]
        bus_r = globconf.BUS_BRACKETS[1]
        delim = globconf.SUBNET_DELIMITER
        subname = full_name
        index = ""
        if bus_l in subname and bus_r in subname:
            subname, index = subname.split(bus_l, maxsplit=1)
            index = index.strip()
            index = remove_suffix(index, bus_r)
        suffix = ""    
        if delim in subname:
            subname, suffix = subname.split(delim, maxsplit=1)
        return cls(subname, suffix=suffix, index=index)

class Pin(ConnectionBit[Union[PlacedPin,LayPin,None],Union[NetlistPin,None]]):
    def __str__(self):
        return f"Pin:{self.full_name}"
    
class Net(ConnectionBit[Union[LayNet,None],Union[NetlistNet,None]]):
    def __init__(self, name, suffix = None, index = None, full_name_layout=True, full_name_netlist=True):
        super().__init__(name, suffix=suffix, index=index, 
                         full_name_layout=full_name_layout, 
                         full_name_netlist=full_name_netlist)
        self.pin:Union[Pin,None] = None
        
    def __str__(self):
        return f"Net:{self.full_name}"

BUSTYPE = TypeVar("BUSTYPE", bound=ConnectionBit)
class _Bus(List[BUSTYPE]):
    _type:Type[BUSTYPE] = ConnectionBit
    def __init__(self, name:str, size:int, 
                 suffix:Union[str,int] = None,
                 full_name_layout = True,
                 full_name_netlist = True):
        self.name = ConnectionBit(name, suffix=suffix).full_name # Suffixed name
        for bit in range(size):
            self.append(self._type(name, 
                                   index = bit, 
                                   suffix = suffix,
                                   full_name_layout = full_name_layout,
                                   full_name_netlist = full_name_netlist))
    def connection(self, base_name:str, 
                   stop = None,
                   start = 0, 
                   step = 1) -> Dict[str,BUSTYPE]:
        " Create bit-by-bit connection {base_name[0]:this[0],...}"
        if stop is None:
            stop = len(self)
        if stop == 0:
            return {}
        if stop > len(self):
            raise IndexError(f"Stop value must not exceed {len(self)}")
        res:Dict[str,BUSTYPE] = {}
        for bit in range(start, stop, step):
            res[ConnectionBit(base_name, index=bit).full_name] = self[bit]
        
class NetBus(_Bus[Net]): 
    _type = Net
    
class PinBus(_Bus[Pin]):
    _type = Pin
        