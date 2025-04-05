from __future__ import annotations
from typing import Any, Dict, List
from typing import overload
from pathlib import Path
import logging
from dataclasses import dataclass

from ..configurations import GlobalLayoutConfigs as config
from ..configurations.layout_global_configs import Layer
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
    layout.technology_name = config.TECH_NAME
    layout.read(path)
    return layout


class LayPinInfo():
    def __init__(self, pin_layer:Layer, lbl_layer:Layer) -> None:
        self.box_data = pin_layer
        self.lbl_data = lbl_layer
    
    def __str__(self):
        return f"({self.box_data}) ({self.lbl_data})"
    
    def __repr__(self):
        return str(self)

class LayPin():
    def __init__(self, box:kdb.Box, 
                 box_layer:Layer,
                 label: kdb.Text,
                 label_layer:Layer,
                 adjust_label = False) -> None:
        self.box:kdb.Box = box
        self.name = label.string
        label_trans = label.trans
        if(adjust_label):
            label_trans = kdb.Trans(x=self.box.center().x, y=self.box.center().y)
            label.trans = label_trans
        self.text = label
        
        self.label_layer = label_layer
        self.box_layer = box_layer

    def __eq__(self, value: object) -> bool:
        return self.name == value.name
    
    def __hash__(self):
        return hash((self.name, self.box, self.info))
    
    def from_trans(self, trans:kdb.Trans):
        return LayPin(self.box.transformed(trans), self.box_layer,
                       self.text.transformed(trans), self.label_layer)
    
    def distance(self, pin:LayPin) -> kdb.Vector:
        p1 = self.box.p1
        p2 = pin.box.p1
        return p1 - p2
    
    def displace(self, vector:kdb.Vector):
        self.box.move(vector)
        self.text.move(vector)

    def match(self, pin:LayPin) -> bool:
        xor = kdb.Region(self.box) ^ kdb.Region(pin.box)
        return xor.is_empty()
    
    def __str__(self):
        return f"{self.name} ({self.box.to_s()})"
    
    def __repr__(self):
        return "PIN: " + str(self)
    

class LayNet():
    def __init__(self, name:str, is_pinned = False) -> None:
        self.name = name
        self.is_pinned = is_pinned
        self.top_pin:LayPin = None
        self.ref_pin:LayPin = None

    def readjust_pin(self):
        if(not self.top_pin):
            return None
        if(not self.ref_pin):
            return None
        self.top_pin.displace(self.ref_pin.distance(self.top_pin))

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"NET: {self} [{self.top_pin} {self.ref_pin}]"


class CustomInstance():
    def __init__(self, name:str, 
                 ref_cell: CustomLayoutCell,
                 parent: CustomLayoutCell,
                 kdb_inst:kdb.Instance) -> None:
        self.ref_cell = ref_cell
        self.parent = parent
        self.kdb_inst = kdb_inst
        self.trans = kdb_inst.trans
        self.movement = kdb.Vector()
        self.name = f"{name} ({self.kdb_inst.to_s()})"
        self.ref_pins = ref_cell.pins
        
        self.terminals = self.get_terminals(ref_cell.pins)
        self.is_pinned = False
        self.label:kdb.Shape = None

    def add_label(self):
        if self.label:
            self.label.delete()
        # Adding top-level label
        lbl_layer = Layer(0, 99)
        lbl_text = kdb.Text(self.name, self._center())
        lbl_shapes = self.parent.kdb_cell.shapes(lbl_layer.info)
        self.label = lbl_shapes.insert(lbl_text)

    def get_terminals(self, pins:Dict[str,LayPin]) -> Dict[str,LayPin]:
        res = {}
        for pin_name, pin_obj in pins.items():
            transformed_pin = pin_obj.from_trans(self.trans)
            res[pin_name] = transformed_pin
        return res
    
    def _center(self) -> kdb.Trans:
        boundary = self.kdb_inst.bbox()
        center = boundary.center()
        return kdb.Trans(x=center.x, y=center.y)

    def connect(self, connections:dict[str,LayNet]):
        if(len(connections) != len(self.terminals)):
            raise CompilerLayoutError(f"Invalid size of connections {len(connections)}")
        for pin_name, terminal in self.terminals.items():
            net = connections[pin_name]
            terminal.displace(self.trans.disp)
            if(not net.ref_pin):
                net.ref_pin = terminal
            else: 
                self.pin_to(terminal, net.ref_pin)
            self.terminals[pin_name] = terminal
        for net in connections.values():
            net.readjust_pin()
            
    def pin_to(self, pin1: LayPin, pin2:LayPin):
        displacement = pin2.distance(pin1) # From pin2 (destination) to pin1 (source)
        if(not self.is_pinned):
            self.kdb_inst.transform(kdb.Trans(displacement))
            self.trans = self.kdb_inst.trans
            # for term in self.terminals.values():
            #     term.displace(displacement)
            self.add_label()
            self.is_pinned = True
        pin1.displace(displacement)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"INST: {self} [{self.terminals}]"

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
            instance = CustomInstance(ref_cell.name, ref_cell, self, inst)
            res[instance.name] = instance 
        return res
    
    def _find_label(self, layer:int, box: kdb.Box) -> kdb.Shape:
        """
        Find a label of a layer within a box, it's used to find pins
        """
        reciter = kdb.RecursiveShapeIterator(self.layout, self.kdb_cell, layer, box)
        res = [s.shape() for s in reciter.each()]
        if(len(res) == 0):
            LOGGER.error(f"No labels on the pin {box.to_s}")
            raise CompilerLayoutError()
        elif(len(res) > 1):
            LOGGER.error(f"More then 1 label on the pin {box.to_s}")
            raise CompilerLayoutError()
        return res[0]
    
    def _get_pins(self) -> Dict[str,LayPin]:
        """
        Collect all labeld pins in the cell
        """
        pins = {}
        for lay_info in config._PIN_LAY:
            box_layer = self.layout.find_layer(lay_info[0].info)
            lbl_layer = self.layout.find_layer(lay_info[1].info)
            for box_shape in self.kdb_cell.each_shape(box_layer):
                if(not isinstance(box_shape.box, kdb.Box)):
                    continue
                label_shape = self._find_label(lbl_layer, box_shape.box)
                pin = LayPin(box_shape.box, lay_info[0],
                             label_shape.text, lay_info[1])
                pins[pin.name] = pin 
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
        custom_inst = CustomInstance(inst_name, cell, self, cell_inst)
        custom_inst.add_label()
        self.instances[inst_name] = custom_inst
        return custom_inst

    def add_pin(self, inst_pin: LayPin, pin_name):
        pin_box = inst_pin.box
        pin_text = inst_pin.text
        box_layer = inst_pin.box_layer.info
        lbl_layer = inst_pin.label_layer.info
        new_lbl_text = kdb.Text(pin_name, pin_text.trans)
        box_shapes = self.kdb_cell.shapes(box_layer)
        lbl_shapes = self.kdb_cell.shapes(lbl_layer)
        new_box_shape = box_shapes.insert(pin_box)
        new_label_shape = lbl_shapes.insert(new_lbl_text)
        lpin = LayPin(new_box_shape.box, inst_pin.box_layer, 
                      new_label_shape.text, inst_pin.label_layer, adjust_label=True)
        lnet = self.add_net(pin_name)
        if(lnet.top_pin):
            raise CompilerLayoutError(f"Pin {lpin} is already regestered for net {lnet}")
        lnet.top_pin = lpin
        self.pins[pin_name] = lpin
        return lpin
    
    def add_net(self, net_name, pin:LayPin = None):
        if(net_name in self.nets):
            return self.nets[net_name]
        lnet = LayNet(net_name)
        self.nets[net_name] = lnet
        return lnet
    
    def __str__(self):
        return self.name

    def __repr__(self):
        return f"CELL: {self} [{self.pins}]"
    
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