#from __future__ import annotations
from typing import Dict, List
import logging
#from dataclasses import dataclass

from ..configurations import _GET_LEAFCELL, Layer
from ..configurations import GlobalLayoutConfigs as config
from ..configurations import GlobalConfigs as globconf
from ..utils.Logging import addStreamHandler

try:
    import klayout.db as kdb
except Exception:
    import pya as kdb
    
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
addStreamHandler(LOGGER, verbose=config.VERBOSE)

R0 = kdb.Trans(0 , False, 0, 0)
R90 = kdb.Trans(3 , False, 0, 0)
R180 = kdb.Trans(2, False, 0, 0)
R270 = kdb.Trans(1, False, 0, 0)

M90 = kdb.Trans(3 , True, 0, 0)
M180 = kdb.Trans(2, True, 0, 0)
M270 = kdb.Trans(1, True, 0, 0)

class LayoutError(BaseException): pass

#@dataclass
class LayoutProblems():
    description:str
    values:List[kdb.Box]

def _load_leafcell(cell_name:str) -> kdb.Layout:
    """
    Read a cell from GDS leafcells
    """
    path = _GET_LEAFCELL(cell_name, config.LEAFCELL_PATH)
    if(path is None):
        raise LayoutError(f"'{cell_name}' not found in your 'LEAFCELL_PATH'")
    layout = kdb.Layout(False)
    layout.technology_name = globconf.TECH_NAME
    tech = layout.technology()
    opt = tech.load_layout_options
    opt.layer_map.assign(config.INPUT_MAPPER)
    opt.create_other_layers = False
    layout.read(path, opt)
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

    def move_to(self, pin: "LayPin"):
        displ = pin.distance(self)
        if displ.x != 0 or displ.y != 0:
            self.transform(kdb.Trans(displ))
    
    def distance(self, pin:"LayPin") -> kdb.Vector:
        p1 = self.box.p1
        p2 = pin.box.p1
        return p1 - p2

    def __eq__(self, value: "LayPin") -> bool:
        return self.name == value.name and self.xor(value).is_empty()
    
    def xor(self, pin:"LayPin") -> kdb.Region:
        xor = kdb.Region(self.box) ^ kdb.Region(pin.box)
        return xor
    
    def __str__(self):
        return f"LPIN:{self.name} ({self.box.to_s()})"
    
    def __repr__(self):
        return str(self)

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
        if(adjust_label):
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
        self.box_shape.transform(kdb.Trans(u=trans.disp))
        self.box = self.box_shape.box

    def _transform_text(self, trans: kdb.Trans):
        self.text_shape.transform(kdb.Trans(u=trans.disp)) # Then other
        self.text = self.text_shape.text
        
    def copy(self):
        return PlacedPin(self.box_shape.dup(), self.text_shape.dup(), adjust_label=True)

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
        return f"LNET:{self.name}"
    
    def __repr__(self):
        return f"{self} [{self.top_pin} {self.ref_pin}]"

class CustomInstance():
    def __init__(self, name:str, 
                 ref_cell: "CustomLayoutCell",
                 parent: "CustomLayoutCell",
                 kdb_inst:kdb.Instance) -> None:
        self.ref_cell = ref_cell
        self.parent = parent
        self.kdb_inst = kdb_inst
        self.trans = kdb_inst.trans
        self.movement = kdb.Vector()
        self.name = name
        #self.lable_name = f"{name} ({self.kdb_inst.to_s()})"
        self.ref_pins = ref_cell.pins
        
        self.terminals = self.get_terminals(ref_cell.pins)
        self.nets:Dict[str, LayNet] = {}
        self.is_pinned = False
        self.label:kdb.Shape = None

    def add_label(self):
        if config.INSTANCE_LABEL_LAYER is None:
            return None
        if self.label:
            self.label.delete()
        # Adding top-level label
        lable_name = f"{self.name}"
        lbl_text = kdb.Text(lable_name, self._center())
        lbl_shapes = self.parent.kdb_cell.shapes(config.INSTANCE_LABEL_LAYER)
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

    def connect(self, terminal_name:str, net:LayNet):
        terminal = self.terminals[terminal_name]
        self.nets[terminal_name] = net
        # if(net.top_pin):
        #     self.terminals[terminal.name] = net.top_pin
        self.move(net.ref_pin.distance(terminal))

    def move(self, displ: kdb.Vector):
        if displ == kdb.Vector():
            return None
        if(self.is_pinned):
            LOGGER.warning(f"Trying to move already pinned instance {self.name}")
            #return None
        trans = kdb.Trans(displ)
        self.kdb_inst.transform(trans)
        for term in self.terminals.values():
            term_name = term.name
            term.transform(trans)
            if term_name in self.nets:
                net = self.nets[term_name]
                net.readjust_pin()
        self.add_label()
        self.is_pinned = True
        
    def update(self):
        for term_name, net in self.nets.items():
            terminal = self.terminals[term_name]
            # if not terminal.xor(net.ref_pin):
            #     LOGGER.error(f"PIN doesn't match on {net}: {terminal}<->{net.ref_pin}")
            net.readjust_pin()

    def pin_to(self, pin1: LayPin, pin2:LayPin):
        displacement = pin2.distance(pin1) # From pin2 (destination) to pin1 (source)
        if(not self.is_pinned):
            self.move(displacement) # move instance and all other tied
        # pin1.transform(kdb.Trans(displacement))

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"INST: {self} [{self.terminals}]"

class KDBCell():
    def __init__(self, kdb_cell:kdb.Cell):
        self.name = kdb_cell.name
        self.kdb_layout = kdb_cell.layout()
        self.kdb_cell = kdb_cell
        self.nets: Dict[str, LayNet] = {} # store new internal nets
        self.is_empty = self.kdb_cell.is_ghost_cell()
        self.pins:Dict[str, LayPin] = self._get_pins()
        self.cells:Dict[str,KDBCell] = self._map_cells()
        self.instances:Dict[str,CustomInstance] = self._map_instances()
    
    def _map_cells(self) -> Dict[str,"KDBCell"]:
        res:Dict[str,KDBCell] = dict()
        for cl_ind in self.kdb_cell.each_child_cell():
            child_cell = self.kdb_layout.cell(cl_ind)
            cell_name = child_cell.name
            loaded_cell = KDBCell(child_cell)
            # if(child_cell.is_ghost_cell()):
            #     # If empty, replace content with the leafcell
            #     loaded_cell = LayLeafCell(cell_name) # Read cell from leafcells
            #     self.layout.prune_cell(cl_ind, -1) # Remove initial cell
            #     self._add_cell(loaded_cell)
            res[cell_name] = loaded_cell
        return res
    
    def _map_instances(self) -> Dict[str, CustomInstance]:
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
        reciter = kdb.RecursiveShapeIterator(self.kdb_layout, self.kdb_cell, layer, box)
        res = [s.shape() for s in reciter.each()]
        if(len(res) == 0):
            # LOGGER.error(f"No labels on the pin {box.to_s()}")
            # raise CompilerLayoutError()
            return None
        elif(len(res) > 1):
            LOGGER.error(f"More then 1 label on the pin {box.to_s()}")
            raise LayoutError()
        return res[0]
    
    def _get_pins(self) -> Dict[str,LayPin]:
        """
        Collect all labeld pins in the cell
        """
        pins = {}
        for lay_info in config.PIN_LAY:
            box_layer = self.kdb_layout.find_layer(lay_info[0])
            lbl_layer = self.kdb_layout.find_layer(lay_info[1])
            for box_shape in self.kdb_cell.each_shape(box_layer):
                if(not isinstance(box_shape.box, kdb.Box)):
                    continue
                label_shape = self._find_label(lbl_layer, box_shape.box)
                if label_shape is None:
                    continue
                pin = LayPin(box_shape.box, lay_info[0],
                             label_shape.text, lay_info[1])
                pins[pin.name] = pin 
        return pins
    
    def __str__(self):
        return self.name

    def __repr__(self):
        return f"CELL: {self} [{self.pins}]"
    
    def save(self, filename:str, libname:str = "ic-stitcher"):
        tech = self.kdb_layout.technology()
        opt = tech.save_layout_options
        opt.gds2_write_timestamps = True
        opt.gds2_libname = libname
        self.kdb_layout.write(filename, options=opt)

class CustomLayoutCell(KDBCell):
    def __init__(self, name) -> None:
        """Create a cell represented by a KLayout cell object. 
        If cell_name exists in the library, it will be loaded from the file. 
        If not, empty cell will be created.

        Args:
            cell_name (str): name of the top cell to be created

        Raises:
            ERROR: _description_
        """
        name = name
        layout = kdb.Layout(True)
        layout.create_cell(name)
        super().__init__(layout.top_cell())
    
    def _add_cell(self, cell:"CustomLayoutCell"):
        """ 
        Adding a cell into the current cell tree
        """
        cell_name = cell.name    
        
        if(cell_name in self.cells.keys()):
            return self.cells[cell_name]
        cell_to_add = cell.kdb_cell
        new_cell = self.kdb_layout.create_cell(cell_name)
        new_cell.copy_tree(cell_to_add)
        #self.kdb_cell.copy_tree(new_cell)
        custom_cell = KDBCell(new_cell)
        self.cells[cell_name] = custom_cell
        return custom_cell
    
    def insert(self, inst_name:str, cell:"CustomLayoutCell", 
               trans:kdb.Trans = R0) -> CustomInstance:
        """
        Insert an instance of a cell with inst_name (name) and trans (transformation)
        """
        ref_cell = self._add_cell(cell)
        cell_inst_arr = kdb.CellInstArray(ref_cell.kdb_cell, trans)
        cell_inst = self.kdb_cell.insert(cell_inst_arr)
        custom_inst = CustomInstance(inst_name, cell, self, cell_inst)
        custom_inst.add_label()
        self.instances[inst_name] = custom_inst
        return custom_inst

    def add_pin(self, net:LayNet, pin_name:str):
        inst_pin = net.ref_pin
        new_pin = inst_pin.copy()
        new_pin.text.string = pin_name
        box_shapes = self.kdb_cell.shapes(new_pin.box_layer)
        lbl_shapes = self.kdb_cell.shapes(new_pin.label_layer)
        new_box_shape = box_shapes.insert(new_pin.box)
        new_label_shape = lbl_shapes.insert(new_pin.text)
        #lpin = PlacedPin(new_box_shape, new_label_shape)
        lpin = PlacedPin(new_box_shape, new_label_shape, adjust_label=True)
        if(net.top_pin):
            raise LayoutError(f"Pin {lpin} is already regestered for net {net}")
        net.top_pin = lpin
        self.pins[net.name] = lpin
        return lpin
    
    def add_net(self, net_name, ref_pin: LayPin):
        if(net_name in self.nets):
            return self.nets[net_name]
        lnet = LayNet(net_name, ref_pin)
        self.nets[net_name] = lnet
        return lnet
    
class LayLeafCell(KDBCell):
    def __init__(self, name):
        layout = _load_leafcell(name)
        super().__init__(layout.top_cell())
        LOGGER.debug(f"loading cell '{self.name}' from leafcells")
