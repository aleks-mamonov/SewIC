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

class LayPin(): # Virtual Pin
    def __init__(self, box:kdb.Box, 
                 box_layer:Layer,
                 label: kdb.Text,
                 label_layer:Layer) -> None:
        self.box:kdb.Box = box
        self.name = label.string
        label_trans = label.trans
        self.text:kdb.Text = label
        
        self.label_layer = label_layer
        self.box_layer = box_layer

    def copy(self):
        return LayPin(self.box.dup(), self.box_layer,
                      self.text.dup(), self.label_layer)
    
    def _transform_box(self,trans: kdb.Trans):
        self.box = self.box.transformed(trans)

    def _transform_text(self,trans: kdb.Trans):
        # new = kdb.Text(self.text.string, trans)
        self.text = self.text.transformed(trans)

    def transform(self,trans: kdb.Trans):
        self._transform_box(trans)
        self._transform_text(trans)

    def move_to(self, pin: LayPin):
        displ = pin.distance(self)
        self.transform(kdb.Trans(displ))
    
    def distance(self, pin:LayPin) -> kdb.Vector:
        p1 = self.box.p1
        p2 = pin.box.p1
        return p1 - p2

    def __eq__(self, value: LayPin) -> bool:
        return self.name == value.name and self.match(value)
    
    def match(self, pin:LayPin) -> bool:
        xor = kdb.Region(self.box) ^ kdb.Region(pin.box)
        return xor.is_empty()
    
    def __str__(self):
        return f"{self.name} ({self.box.to_s()})"
    
    def __repr__(self):
        return "PIN: " + str(self)

class PlacedPin(LayPin): # Shape-based, to be able to move
    def __init__(self, box_shape:kdb.Shape, text_shape:kdb.Shape, 
                 adjust_label=False):
        box_layer = Layer(box_shape.layer_info.layer, box_shape.layer_info.datatype,
                          box_shape.layer_info.name)
        label_layer = Layer(text_shape.layer_info.layer, text_shape.layer_info.datatype,
                          text_shape.layer_info.name)
        super().__init__(box_shape.box, box_layer, text_shape.text, label_layer)
        self.box_shape = box_shape
        self.text_shape = text_shape
        self.cell = box_shape.cell
        if(adjust_label): # TODO: lable is not revolved
            self.center_label()
            pass
    
    def center_label(self):
        box_center = self.box.center()
        rot = R0.rot - self.text.trans.rot
        self.text_shape.transform(kdb.Trans(rot=rot)) # Rotate first to 0 - trans.rot
        self.text = self.text_shape.text
        text_point = self.text.position()
        displ = box_center - text_point
        self.text_shape.transform(kdb.Trans(displ)) # Then displacment
        self.text = self.text_shape.text

    def _transform_box(self, trans: kdb.Trans):
        #super()._transform_box(trans)
        # self.box_shape.delete()
        # all = self.cell.shapes(self.box_layer.info)
        # self.box_shape = all.insert(self.box)
        self.box_shape.transform(kdb.Trans(u=trans.disp))
        self.box = self.box_shape.box

    def _transform_text(self, trans: kdb.Trans):
        # super()._transform_text(trans)
        # self.text_shape.delete()
        # all = self.cell.shapes(self.label_layer.info)
        # self.text_shape = all.insert(self.text)
        #self.text_shape.transform(kdb.Trans(rot=trans.rot)) # Rotate first
        #self.text = self.text_shape.text
        #displace = trans.disp - self.text.trans.disp
        self.text_shape.transform(kdb.Trans(u=trans.disp)) # Then other
        self.text = self.text_shape.text


class LayNet():
    def __init__(self, name:str, ref_pin:LayPin) -> None:
        self.name = name
        self.top_pin:PlacedPin = None
        self.ref_pin:LayPin = ref_pin

    def readjust_pin(self):
        if(not self.top_pin):
            return None
        if(not self.ref_pin):
            return None
        #displ = self.ref_pin.distance(self.top_pin)
        self.top_pin.move_to(self.ref_pin)

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
            terminal = pin_obj.copy()
            terminal.transform(self.trans)
            res[pin_name] = terminal
        return res
    
    def _center(self) -> kdb.Trans:
        boundary = self.kdb_inst.bbox()
        center = boundary.center()
        return kdb.Trans(x=center.x, y=center.y)

    def connect(self, connections:dict[str,LayNet]):
        if(len(connections) != len(self.terminals)):
            raise CompilerLayoutError(f"Invalid size of connections {len(connections)}")
        displacement = None
        for pin_name, terminal in self.terminals.items():
            net = connections[pin_name]
            #terminal.displace(self.trans.disp)
            if(not net.ref_pin):
                net.ref_pin = terminal
            else: 
                displacement = net.ref_pin.distance(terminal)
            if(net.top_pin):
                self.terminals[pin_name] = net.top_pin
        if(displacement):
            self.move(displacement)
                #self.pin_to(terminal, net.ref_pin)
            #self.terminals[pin_name] = terminal
        # for net in connections.values():
        #     net.readjust_pin()

    def move(self, displ: kdb.Vector):
        if(self.is_pinned):
            return None
        trans = kdb.Trans(displ)
        self.kdb_inst.transform(trans)
        for term in self.terminals.values():
            term.transform(trans)
        self.add_label()
        self.is_pinned = True

    def pin_to(self, pin1: LayPin, pin2:LayPin):
        displacement = pin2.distance(pin1) # From pin2 (destination) to pin1 (source)
        if(not self.is_pinned):
            self.move(displacement) # move instance and all other tied
        # pin1.transform(kdb.Trans(displacement))

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

    def add_pin(self, net:LayNet):
        inst_pin = net.ref_pin
        pin_name = net.name
        new_pin = inst_pin.copy()
        new_pin.text.string = pin_name
        box_shapes = self.kdb_cell.shapes(new_pin.box_layer.info)
        lbl_shapes = self.kdb_cell.shapes(new_pin.label_layer.info)
        new_box_shape = box_shapes.insert(new_pin.box)
        new_label_shape = lbl_shapes.insert(new_pin.text)
        #lpin = PlacedPin(new_box_shape, new_label_shape)
        lpin = PlacedPin(new_box_shape, new_label_shape, adjust_label=True)
        if(net.top_pin):
            raise CompilerLayoutError(f"Pin {lpin} is already regestered for net {net}")
        net.top_pin = lpin
        self.pins[pin_name] = lpin
        return lpin
    
    def add_net(self, net_name, ref_pin: LayPin):
        if(net_name in self.nets):
            return self.nets[net_name]
        lnet = LayNet(net_name, ref_pin)
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