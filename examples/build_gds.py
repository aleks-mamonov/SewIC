from __future__ import annotations
import os
from pathlib import Path
import klayout_plugin.configuration
import klayout_plugin.ic_stitcher.custom_cell as ip

class TestCell(ip.CustomCell):
    def __init__(self, cell_name, p = 0):
        super().__init__(cell_name)
        self.declare(ip.Pin("in"), ip.Pin("out"))

    def declare(X, inp, out, p = 0):
        n_mos = ip.LeafCell('n_mos')
        p_mos = ip.LeafCell('p_mos')
        X['nm'] = ip.Item(n_mos,{"S":"S_net","D":"D_net"})
        X['pm'] = ip.Item(p_mos,{"S":"S_net","D":"D_net"}, trans=ip.R270)
        X['pm_1'] = ip.Item(p_mos,{"S":inp,"D":"D_net"}, trans=ip.R180)
        X['pm_2'] = ip.Item(p_mos,{"S":out,"D":"D_net"}, trans=ip.R90)
        pass
    

def main() -> None:
    builder = TestCell('out')
    builder.claim("./test.gds")
    pass

if __name__ == "__main__":
    main()