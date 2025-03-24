from typing import List, Tuple
from pathlib import Path

class GlobalLayoutConfigs():
    # Define the list of pathes to layout leafcells, 
    # best to use Path().glob(your_path)
    LEAFCELL_PATH:List[Path | str] = []
    
    # Define layer numbers for searching pins and lables
    PIN_LAY:List[Tuple[Tuple[int,int],Tuple[int,int]]] = []

    # KLayout layout object, used for inside-KLayout run
    KLAYOUT = None

