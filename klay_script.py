import pya

# Makes KLayout debug possible: update of the loaded modules
from importlib import reload
import klayout_plugin.ic_stitcher.layout.floorplaner  as layout
import klayout_plugin.subcells.build_gds as bl
reload(bl)
reload(layout)
#######################

def main():
    mw = pya.Application.instance().main_window()
    #lw = mw.view(mw.create_view())
    #layout = 
    cell_view = mw.create_layout(0)
    lay_view = cell_view.view()
    lay_view.active_setview_index = cell_view.cell_index
    lay = cell_view.layout()
    #c = lay.create_cell('my')
    builder = bl.TestCell('out', klayout_lay=lay)

if __name__ == "__main__":
    main()