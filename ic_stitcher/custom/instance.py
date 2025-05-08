#from __future__ import annotations
import logging
from typing import Union, Dict
from abc import ABC

from ic_stitcher.layout.floorplaner import * 
from ic_stitcher.schematic.netlister import * 
from ic_stitcher.utils.Logging import addStreamHandler
#import klayout_plugin.ip_builder.schematic.netlister as netlist


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
