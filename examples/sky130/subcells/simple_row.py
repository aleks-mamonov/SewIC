from __future__ import annotations
import os
from pathlib import Path
from ..configuration import *
import ic_stitcher as ic

class TestCell(ic.CustomCell):
    def __init__(self, cell_name, p = 0):
        super().__init__(cell_name)
        self.top(ic.Pin("in"), ic.Pin("out"))

    def top(X, inp, out, p = 0):
        n_mos = ic.LeafCell('n_mos')
        p_mos = ic.LeafCell('p_mos')
        s_net = ic.Net("s_net")
        d_net = ic.Net("d_net")
        a_net = ic.Net("a_net")
        X['nm'] = ic.Item(n_mos,{"S":out,"D":d_net}, trans=ic.R180)
        X['pm'] = ic.Item(p_mos,{"S":s_net,"D":d_net,"A":inp})
        #X['nm1'] = ip.Item(n_mos,{"S":out,"D":"A_net"}, trans=ip.R180)
        # X['pm_1'] = ip.Item(p_mos,{"S":inp,"D":"D_net"}, trans=ip.R180)
        # X['pm_2'] = ip.Item(p_mos,{"S":"S_net","D":"D_net"}, trans=ip.R90)
        pass
    

def main() -> None:
    builder = TestCell('out')
    builder.claim("./test.gds")
    pass

if __name__ == "__main__":
    main()