from __future__ import annotations
from typing import Any, Dict, List
from typing import overload
from pathlib import Path
import logging
from dataclasses import dataclass

from ..configurations import GlobalLayoutConfigs as config
import klayout.db as kdb

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

R0 = kdb.Trans(0 , False, 0, 0)
R90 = kdb.Trans(3 , False, 0, 0)
R180 = kdb.Trans(2, False, 0, 0)
R270 = kdb.Trans(1, False, 0, 0)

M90 = kdb.Trans(3 , True, 0, 0)
M180 = kdb.Trans(2, True, 0, 0)
M270 = kdb.Trans(1, True, 0, 0)

class CompilerLayoutError(BaseException): pass

def _MAP_LEAFCELLS() -> Dict[str,Path]:
    res_dict = {}
    for netlist_path in config.LEAFCELL_PATH:
        netlist_path = Path(netlist_path)
        res_dict[netlist_path.stem] = netlist_path
    return res_dict

LEAFCELLS = _MAP_LEAFCELLS()

def _load_leafcell(call_name:str) -> kdb.Layout:
    """
    Read a cell from GDS leafcells
    """
    path = LEAFCELLS.get(call_name)
    if(path is None):
        LOGGER.error(f"'{call_name}' not found in {config.LEAFCELL_PATH}")
    layout = kdb.Layout(False)
    layout.read(path)
    return layout

class Layer():
    def __init__(self, layer:int, datatype:int) -> None:
        self.info = kdb.LayerInfo(layer, datatype)
        pass

class LayPinInfo():
    def __init__(self, pin_layer:Layer, lbl_layer:Layer) -> None:
        self.box_data = pin_layer
        self.lbl_data = lbl_layer

LAY_PIN_INFOS:List[LayPinInfo] = [
    LayPinInfo(Layer(ps[0][0],ps[0][1]), 
               Layer(ps[1][0],ps[1][1])) for ps in config.PIN_LAY]

class LayPin():
    def __init__(self, text:kdb.Text, box:kdb.Box, info:LayPinInfo) -> None:
        self.box = box
        self.text = text
        self.lable = text.string
        self.info = info
        self.is_pinned = False

    def __eq__(self, value: object) -> bool:
        return self.lable == value.lable
    
    def __hash__(self):
        return hash((self.lable, self.box, self.info))
    
    def from_trans(self, trans:kdb.Trans):
        return LayPin(self.text.transformed(trans),
                      self.box.transformed(trans),
                      self.info)
    
    def distance(self, pin:LayPin) -> kdb.Vector:
        p1 = self.box.p1
        p2 = pin.box.p1
        return p1 - p2
    
    def displace(self, vector:kdb.Vector):
        self.box.move(vector)

    def match(self, pin:LayPin) -> bool:
        xor = kdb.Region(self.box) ^ kdb.Region(pin.box)
        return xor.is_empty()
    
    def __str__(self):
        return f"{self.lable} ({self.box.to_s()})"
    
class LayNet():
    def __init__(self, name:str) -> None:
        self.name = name
        self.pins = []
        self.connections:dict[str,CustomInstance] = {}

    def bound(self, pin:str, inst:CustomInstance):
        self.connections[pin] = inst

class CustomInstance():
    def __init__(self, name:str, instance:kdb.Instance, ref_cell: CustomLayoutCell) -> None:
        self.kdb_cell = instance.cell
        self.trans = instance.trans
        self.kdb_inst = instance
        self.name = f"{self.kdb_cell.name} ({self.kdb_inst.to_s()})"
        self.ref_pins = self.replace(ref_cell.pins)
        self.is_pinned = False
        self.terminals:dict[str, LayPin | LayNet] = {}

    def replace(self, pins:Dict[str,LayPin]) -> Dict[str,LayPin]:
        res = {}
        for pin_name, pin_obj in pins.items():
            transformed_pin = pin_obj.from_trans(self.trans)
            res[pin_name] = transformed_pin
        return res
    
    def connect_to_net(self, terminal:str, net:LayNet):
        for pin_ref, inst_ref in net.connections.items():
                self.pin_to(inst_ref, terminal, pin_ref)
                self.terminals[pin_ref] = net

    def pin_to(self, inst:CustomInstance, p1:str, p2:str):
        pin1 = self.ref_pins.get(p1)
        if(pin1 is None):
            LOGGER.error(f"No PIN {p1} found in {self.name}")
            raise CompilerLayoutError()
        pin2 = inst.ref_pins.get(p2)
        if(pin2 is None):
            LOGGER.error(f"No PIN {p2} in {inst.name}")
            raise CompilerLayoutError()
        
        if(self.is_pinned):
            if(not pin1.match(pin2)):
                LOGGER.error(f"unmatched pins in {self.name} {pin1} <> {pin2}")
                #raise CompilerLayoutError()
        else:
            displacement = pin2.distance(pin1)
            self.kdb_inst.transform(kdb.Trans(displacement))
            self.trans = self.kdb_inst.trans
            self.ref_pins = self.replace(self.ref_pins)
            self.is_pinned = True

class CustomLayoutCell():
    def __init__(self, name) -> None:
        """Create a cell represented by a KLayout cell object. 
        If cell_name exists in the library, it will be loaded from the file. 
        If not, empty cell will be created.

        Args:
            cell_name (str): name of the top cell to be loaded

        Raises:
            ERROR: _description_
        """
        self.name = name
        self.layout = kdb.Layout(True)
        self.layout.create_cell(name)
        self.kdb_cell = self.layout.top_cell()
        self.top_cell_id = self.layout.cell_by_name(self.name)
        self.nets: dict[str, LayNet] = {} # store new internal nets
        self.is_empty = True
        self.pins = {}
        self.cells:Dict[str,KDBCell] = {}
        self.instances:Dict[str,CustomInstance] = {}

    def _map_content(self) -> None:
        self.is_empty = self.kdb_cell.is_ghost_cell()
        self.pins = self._get_pins()
        self.cells = self._map_cells()
        self.instances = self._map_instances()
    
    def _map_cells(self) -> dict[str,KDBCell]:
        res:dict[str,KDBCell] = dict()
        for cl_ind in self.kdb_cell.each_child_cell():
            child_cell = self.layout.cell(cl_ind)
            cell_name = child_cell.name
            loaded_cell = KDBCell(child_cell)
            # if(child_cell.is_ghost_cell()):
            #     # If empty, replace content with the leafcell
            #     loaded_cell = LayLeafCell(cell_name) # Read cell from leafcells
            #     self.layout.prune_cell(cl_ind, -1) # Remove initial cell
            #     self._add_cell(loaded_cell)
            res[cell_name] = loaded_cell
        return res
    
    def _map_instances(self) -> dict[str, CustomInstance]:
        res = dict()
        for inst in self.kdb_cell.each_inst():
            cell_reference:kdb.Cell = inst.cell
            cell_name = cell_reference.name
            ref_cell = self.cells[cell_name]
            instance = CustomInstance(inst.to_s(), inst, ref_cell)
            res[instance.name] = instance 
        return res
    
    def _find_lable(self, layer:int, box: kdb.Box) -> kdb.Shape:
        """
        Find a lable of a layer within a box, it's used to find pins
        """
        reciter = kdb.RecursiveShapeIterator(self.layout, self.kdb_cell, layer, box)
        res = [s.shape() for s in reciter.each()]
        if(len(res) == 0):
            LOGGER.error(f"No lables on the pin {box.to_s}")
            raise CompilerLayoutError()
        elif(len(res) > 1):
            LOGGER.error(f"More then 1 lable on the pin {box.to_s}")
            raise CompilerLayoutError()
        return res[0]
    
    def _get_pins(self) -> Dict[str,LayPin]:
        """
        Collect all labled pins in the cell
        """
        pins = {}
        for lay_info in LAY_PIN_INFOS:
            pin_layer = self.layout.find_layer(lay_info.box_data.info)
            lbl_layer = self.layout.find_layer(lay_info.lbl_data.info)
            for pin in self.kdb_cell.each_shape(pin_layer):
                sbox = pin.box
                lable_shape = self._find_lable(lbl_layer, sbox)
                text:kdb.Text = lable_shape.text
                pins[text.string] = LayPin(text, sbox, lay_info)
        return pins
    
    def _add_cell(self, cell:CustomLayoutCell):
        """ 
        Adding a cell into the current cell tree
        """
        cell_name = cell.name    
        
        if(cell_name in self.cells.keys()):
            return self.cells[cell_name]
        cell_to_add = cell.kdb_cell
        new_cell = self.kdb_cell.layout().create_cell(cell_name)
        new_cell.copy_tree(cell_to_add)
        #self.kdb_cell.copy_tree(new_cell)
        custom_cell = KDBCell(new_cell)
        self.cells[cell_name] = custom_cell
        return custom_cell
    
    def insert(self, cell:CustomLayoutCell, inst_name:str,
               trans:kdb.Trans = R0) -> CustomInstance:
        """
        Insert an instance of cell with inst_name (name) and trans (transformation)
        """
        ref_cell = self._add_cell(cell)
        cell_inst_arr = kdb.CellInstArray(ref_cell.kdb_cell, trans)
        cell_inst = self.kdb_cell.insert(cell_inst_arr)
        custom_inst = CustomInstance(inst_name, cell_inst, cell)
        self.instances[inst_name] = custom_inst
        return custom_inst
    
    def connect_to_net(self, instance: CustomInstance, terminal:str, net_name: str):
        lnet:LayNet = self.nets.get(net_name)
        if(lnet is None):
            lnet = LayNet(net_name)
            lnet.bound(terminal,instance)
            self.nets[net_name] = lnet
        else:
            for pin_ref, inst_ref in lnet.connections.items():
                instance.pin_to(inst_ref, terminal, pin_ref)

    def connect_to_pin(self, instance: CustomInstance, terminal:str, pin_name: str):
        if(pin_name in self.pins):
            raise CompilerLayoutError(f"Pin {pin_name} is already regestered")
        inst_pin = instance.ref_pins[terminal]
        pin_box = inst_pin.box
        pin_text = inst_pin.text
        box_layer = inst_pin.info.box_data.info
        lbl_layer = inst_pin.info.lbl_data.info
        new_lbl_text = kdb.Text(pin_name, pin_text.trans)
        box_shapes = self.kdb_cell.shapes(box_layer)
        lbl_shapes = self.kdb_cell.shapes(lbl_layer)
        box_shapes.insert(pin_box)
        lbl_shapes.insert(new_lbl_text)
        self.pins[pin_name] = LayPin(new_lbl_text, pin_box, inst_pin.info)
    

    def attach_pin(self, net_name: str):
        net = self.nets[net_name]
        connections = net.connections.items()
        for pin_name, inst in connections:
            pin = inst.ref_pins[pin_name]
            pin_box = pin.box
            pin_text = pin.text
            box_layer = pin.info.box_data.info
            lbl_layer = pin.info.lbl_data.info
            new_lbl_text = kdb.Text(net_name, pin_text.trans)
            box_shapes = self.kdb_cell.shapes(box_layer)
            lbl_shapes = self.kdb_cell.shapes(lbl_layer)
            box_shapes.insert(pin_box)
            lbl_shapes.insert(new_lbl_text)
            net.bound(net_name, LayPin(new_lbl_text, pin_box, pin.info))

class LayLeafCell(CustomLayoutCell):
    def __init__(self, name):
        super().__init__(name)
        LOGGER.debug(f"loading cell '{self.name}' from leafcells")
        self._reinit(_load_leafcell(self.name))
    
    def _reinit(self, layout: kdb.Layout):
        self.layout._destroy()
        self.layout = layout
        self.kdb_cell = self.layout.top_cell()
        self.cell_id = self.layout.cell_by_name(self.name)
        self._map_content()

class KDBCell(CustomLayoutCell):
    def __init__(self, kdb_cell:kdb.Cell):
        super().__init__(kdb_cell.name)
        LOGGER.debug(f"loading cell '{self.name}' from existing cell")
        self._reinit(kdb_cell)

    def _reinit(self, cell: kdb.Cell):
        self.layout._destroy()
        self.layout = cell.layout()
        self.kdb_cell = cell
        self.cell_id = self.layout.cell_by_name(self.name)
        self._map_content()