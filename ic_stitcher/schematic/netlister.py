from __future__ import annotations
import klayout.db as kdb
from pathlib import Path
from typing import Any, List, Dict, Sequence, Self
import logging

from ..configurations import GlobalSchematicConfigs as config
from ..utils.Logging import addStreamHandler

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
addStreamHandler(LOGGER)

class NetlisterError(BaseException): ...

def _MAP_LEAFCELLS() -> Dict[str,Path]:
    res_dict = {}
    for netlist_path in config.LEAFCELL_PATH:
        res_dict[netlist_path.stem] = netlist_path
    return res_dict

LEAFCELL_DICT = _MAP_LEAFCELLS()  

class CustomNetlistReader(kdb.NetlistSpiceReaderDelegate):

    def wants_subcircuit(self, name: str) -> bool:
        for primitive_device in config.NETLIST_PRIMITIVES:
            if(name == primitive_device):
                return True
        return False
    
    # def element(self, circuit: kdb.Circuit, 
    #             el: str, name: str, 
    #             model: str, value: float, 
    #             nets: Sequence[kdb.Net], 
    #             params: Dict[str, Any]) -> bool:
    #     if(el != "X"):
    #         # all other elements are left to the standard implementation
    #         return super().element(circuit, el, name, model, value, nets, params)
    #     cell = CustomNetlistCell(circuit)
    #     if(cell.is_ghost()):
    #         cell.read_from_netlist()
    #     return super().element(circuit, el, name, model, value, nets, params)

def _load_leafcell(cell_name:str) -> kdb.Netlist:
    path_to_netlist = LEAFCELL_DICT[cell_name]
    if(not path_to_netlist.exists()):
        raise NetlisterError(f"Failed to find leafcell for '{cell_name}'")
    reader_deligate = CustomNetlistReader()
    netlist_reader = kdb.NetlistSpiceReader(reader_deligate)
    netlist = kdb.Netlist()
    netlist.read(str(path_to_netlist.resolve()), netlist_reader)
    return netlist

class NetlistPin():
    def __init__(self, kdb_pin:kdb.Pin) -> None:
        self.kdb_pin = kdb_pin
        self.name = kdb_pin.name()
        self.id = kdb_pin.id()
    
    def copy(self):
        return NetlistPin(self.kdb_pin.dup())

class NetlistNet():
    def __init__(self, kdb_net:kdb.Net, pin:NetlistPin = None) -> None:
        self.kdb_net = kdb_net
        self.name = kdb_net.name
        self.pin = pin
        self.id = kdb_net.cluster_id

class CustomNetlistInstance():
    def __init__(self, kdb_subcircuit:kdb.SubCircuit, ref_cell:KDBNetlistCell, parent:KDBNetlistCell) -> None:
        self.name = kdb_subcircuit.name
        self.kdb_subcircuit = kdb_subcircuit
        self.ref_cell = ref_cell
        self.parent = parent
    
    def connect(self, ref_pin_name:str, net: NetlistNet):
        ref_pin = self.ref_cell.pins[ref_pin_name]
        self.kdb_subcircuit.connect_pin(ref_pin.kdb_pin, net.kdb_net)
        
class CustomDevice():
    def __init__(self, kdb_device:kdb.Device) -> None:
        self.name = kdb_device.name
        self.kdb_device = kdb_device
        
class KDBNetlistCell():
    def __init__(self, kdb_netlist:kdb.Netlist, kdb_cell:kdb.Circuit):
        self.kdb_netlist = kdb_netlist
        self.kdb_circuit = kdb_cell
        self.name = kdb_cell.name
        self.pins, self.orderd_pins = self._find_pins()
        self.nets = self._find_nets()
        self.instances = self._find_instances()
        self.devices = self._find_devices()
        self.ref_cells:dict[str, KDBNetlistCell] = {}
    
    def find_circuit(self, cell_name:str) -> kdb.Circuit:
        return self.kdb_netlist.circuit_by_name(cell_name)
    
    def _fetch_cell(self, name:str):
        if name in self.ref_cells:
            return self.ref_cells[name]
        internal = self.find_circuit(name)
        if internal is not None:
            cell = KDBNetlistCell(internal.netlist(), internal)
            self.ref_cells[cell.name] = cell
            return cell
        leafcell = LeafNetlistCell(name)
        self.ref_cells[leafcell.name] = leafcell
        return cell
    
    def _find_pins(self) -> tuple[Dict[str,NetlistPin], list[NetlistPin]]:
        res:Dict[str:NetlistPin] = {}
        ordered = []
        for ind, pin in enumerate(self.kdb_circuit.each_pin()):
            custom = NetlistPin(pin)
            ordered.append(custom)
            res[custom.name] = custom
        return res, ordered
    
    def _find_nets(self) -> Dict[str,NetlistNet]:
        res:Dict[str:NetlistNet] = {}
        for net in self.kdb_circuit.each_net():
            if net.name in self.pins:
                pin = self.pins[net.name]
                custom = NetlistNet(net, pin)
            else:
                custom = NetlistNet(net)
            res[custom.name] = custom
        return res    
    
    def _find_instances(self) -> Dict[str,CustomNetlistInstance]:
        res:Dict[str:CustomNetlistInstance] = {}
        for sub in self.kdb_circuit.each_subcircuit():
            ref_cell = self._fetch_cell(sub.circuit_ref().name)
            res[sub.name] = CustomNetlistInstance(sub, ref_cell, self)
        return res    
    
    def _find_devices(self) -> Dict[str,CustomDevice]:
        res:Dict[str:CustomDevice] = {}
        for device in self.kdb_circuit.each_device():
            #ref_cell = self._fetch_cell(device.circuit().name)
            res[device.name] = CustomDevice(device)
        return res   
    
    def save(self, file:str, description:str = None):
        netlist_writer = kdb.NetlistSpiceWriter()
        netlist_writer.use_net_names = config.SAVE_USE_NET_NAMES
        netlist_writer.with_comments = config.SAVE_WITH_COMMENTS
        self.kdb_netlist.write(file, netlist_writer, description=description)
            
class CustomNetlistCell(KDBNetlistCell):
    # loaded_cell:Dict[str:kdb.Circuit] = {}
    def __init__(self, name:str) -> None:
        # Create a new cell
        kdb_netlist = kdb.Netlist()
        top_cell = kdb.Circuit()
        top_cell.name = name
        kdb_netlist.add(top_cell)
        super().__init__(kdb_netlist, top_cell)
        
    def add_net(self, net_name:str):
        if config.SUBNET_DELIMITER:
            if(net_name.find(config.SUBNET_DELIMITER) != -1):
                net_name = net_name.split(config.SUBNET_DELIMITER)[0]
        if net_name in self.nets:
            return self.nets[net_name]
        kdb_net = self.kdb_circuit.create_net(net_name)
        net = NetlistNet(kdb_net)
        self.nets[net.name] = net
        return net
        
    def add_pin(self, net:NetlistNet):
        pin_name = net.name
        if pin_name in self.pins:
            raise NetlisterError(f"Trying to add existing pin '{pin_name}'")
        kdb_pin = self.kdb_circuit.create_pin(pin_name)
        pin = NetlistPin(kdb_pin)
        self.kdb_circuit.connect_pin(kdb_pin, net.kdb_net)
        self.pins[pin.name] = pin
        net.pin = pin
        self.orderd_pins.append(pin)
        return pin
       
    def add(self, cell:CustomNetlistCell|LeafNetlistCell|KDBNetlistCell) -> KDBNetlistCell:
        cellname = cell.name
        new_cell = self.ref_cells.get(cellname)
        if(not new_cell):
            copy:kdb.Circuit = cell.kdb_circuit._dup()
            self.kdb_netlist.add(copy)
            new_cell = self._fetch_cell(cellname)
            for ref_cell in cell.ref_cells.values():
                self.ref_cells[ref_cell.name] = self.add(ref_cell)
        else:
            LOGGER.debug(f"[{self.name}] inserting an existing cell '{cellname}'")
        return new_cell
    
    def insert(self, inst_name:str, cell:CustomNetlistCell|LeafNetlistCell) -> CustomNetlistInstance:
        """
        Insert an instance by cell name and by pins, retriving a reference cell from loaded cells 
        or reading it from leafcells
        """
        ref_cell = self.add(cell)
        sub = self.kdb_circuit.create_subcircuit(ref_cell.kdb_circuit, inst_name)
        self.instances[inst_name] = sub
        return CustomNetlistInstance(sub, ref_cell, self)

class LeafNetlistCell(KDBNetlistCell):
    def __init__(self, name:str):
        netlist = _load_leafcell(name)
        kdb_circuit = netlist.circuit_by_name(name)
        if not kdb_circuit:
            raise NetlisterError(f"Failed to find cell '{name}' in a leafcell")
        super().__init__(netlist, kdb_circuit)
    #     self.ref_cells = self.map_cells()
    
    # def map_cells(self) -> Dict[str:KDBNetlistCell]:
    #     res = {}
    #     for indx, circuit in enumerate(self.kdb_netlist.each_circuit_top_down()):
    #         custom_cell = KDBNetlistCell(circuit)
    #         if(indx == 0):
    #             #self.top_cell = custom_cell
    #             continue
    #         res[custom_cell.name] = custom_cell
    #     return res    
    
