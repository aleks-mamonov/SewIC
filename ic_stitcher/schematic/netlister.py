from __future__ import annotations
import klayout.db as kdb
from pathlib import Path
from typing import Any, List, Dict, Sequence

from klayout_plugin.ic_stitcher.schematic import GlobalSchematicConfigs as config

class NetlisterError(BaseException): ...

def READ_LEAFCELLS() -> Dict[str,Path]:
    res_dict = {}
    for netlist_path in config.LEAFCELL_PATH:
        res_dict[netlist_path.stem] = netlist_path
    return res_dict

LEAFCELL_DICT = READ_LEAFCELLS()  

class NetlistPin():
    def __init__(self, kdb_pin:kdb.Pin, index:int) -> None:
        self.kdb_pin = kdb_pin
        self.name = kdb_pin.name
        self.index = index

class NetlistNet():
    def __init__(self, kdb_net:kdb.Net) -> None:
        self.kdb_net = kdb_net
        self.name = kdb_net.name

class CustomNetlistInstance():
    def __init__(self, kdb_subcircuit:kdb.SubCircuit) -> None:
        self.inst = kdb_subcircuit

class CustomNetlistCell():
    # loaded_cell:Dict[str:kdb.Circuit] = {}
    def __init__(self, circuit:kdb.Circuit) -> None:
        self.kdb_circuit = circuit
        self.netlist = circuit.netlist()
        self.name = circuit.name
        # if(self.name in self.loaded_cell.keys()):
        #     self.kdb_circuit = self.loaded_cell[self.name]
        # else:
        #     self.loaded_cell[self.name] = self.kdb_circuit
        self.pins = self.get_pins()
        self.nets = self.get_nets()

    def get_pins(self) -> List[NetlistPin]:
        res:Dict[str:NetlistPin] = []
        for ind,pin in enumerate(self.kdb_circuit.each_pin()):
            res[pin.name] = NetlistPin(pin, ind)
        return res
    
    def get_nets(self):
        res:Dict[str:NetlistNet]
        for net in self.kdb_circuit.each_net():
            res[net.name] = NetlistNet(net)
        return res
    
    def create_net(self, name:str):
        pass
    
    def is_ghost(self):
        return bool(list(self.kdb_circuit.each_net()))
    

class CustomNetlistReader(kdb.NetlistSpiceReaderDelegate):

    def wants_subcircuit(self, name: str) -> bool:
        for pr in config.NETLIST_PRIMITIVES:
            if(name == pr):
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


class CustomNetlist():
    loaded_cells:Dict[str:CustomNetlistCell] = {}
    def __init__(self, cell_name:str) -> None:
        self.top_cell_name = cell_name
        if(cell_name in LEAFCELL_DICT.keys()):
            self.kdb_netlist:kdb.Netlist = self.read_leafnetlist(LEAFCELL_DICT[cell_name])
        else:
            self.kdb_netlist = kdb.Netlist()
            top_cell = kdb.Circuit()
            top_cell.name = cell_name
            self.kdb_netlist.add(top_cell)
        self.cell_map:Dict[str:CustomNetlistCell] = self.map_cells()
    
    def read_leafnetlist(self, path_to_netlist:Path) -> kdb.Netlist:
        netlist_reader = CustomNetlistReader()
        netlist = kdb.Netlist()
        netlist.read(str(path_to_netlist.resolve()), netlist_reader)
        return netlist
    
    def find_circuit(self, cell_name:str) -> CustomNetlistCell:
        new_cell = self.loaded_cells.get(cell_name)
        if(new_cell):
            return new_cell
        leafneatlist = CustomNetlist(cell_name)
        new_cell = leafneatlist.top_cell
        if(new_cell.is_ghost()):
            raise ValueError(f"Error: cell {new_cell.name} is not found")
        return new_cell
    
    def map_cells(self) -> Dict[str:CustomNetlistCell]:
        res = {}
        for indx, circuit in enumerate(self.kdb_netlist.each_circuit_top_down()):
            custom_cell = CustomNetlistCell(circuit)
            if(indx == 0):
                self.top_cell = custom_cell
                if(self.top_cell.is_ghost()):
                    raise NetlisterError(f"Top Cell {self.top_cell.name} must not be empty")
                self.loaded_cells[custom_cell.name] = custom_cell
                continue
            if(custom_cell.is_ghost()):
                new_cell = self.find_circuit(custom_cell.name)
                self.kdb_netlist.remove(custom_cell)
                self.kdb_netlist.add(new_cell)
            self.loaded_cells[custom_cell.name] = custom_cell
            res[custom_cell.name] = custom_cell
        return res
    
    def add(self, cell_name:str) -> CustomNetlistCell:
        cell = self.cell_map.get(cell_name)
        if(not cell):
            cell = self.find_circuit(cell_name)
            self.kdb_netlist.add(cell.kdb_circuit)
            self.cell_map[cell.name] = cell
        return cell
    
    def insert(self, inst_name:str, cell_name:str, **connection:Dict[str:str]):
        """
        Insert an instance by cell name and by pins, retriving a reference cell from loaded cells 
        or reading it from leafcells
        """
        ref_cell = self.add(cell_name)
        sub = self.top_cell.kdb_circuit.create_subcircuit(ref_cell.kdb_circuit, inst_name)
        self.top_cell.kdb_circuit.each_pin()
        for pin_conn, net_conn in connection.items():
            pin = ref_cell.pins[pin_conn]
            net = self.top_cell.nets[net_conn]
            sub.connect_pin(pin, net)
    
    def save(self, file:str, description:str = None):
        netlist_writer = kdb.NetlistSpiceWriter()
        netlist_writer.use_net_names = config.USE_NET_NAMES
        netlist_writer.with_comments = config.WITH_COMMENTS
        self.kdb_netlist.write(file, netlist_writer, description=description)
