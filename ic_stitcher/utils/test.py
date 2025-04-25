import klayout.db as kdb

netlist1 = kdb.Netlist()
circ1 = kdb.Circuit()
circ1.name = "test1"
netlist1.add(circ1)
#netlist1.write("test1.cir", kdb.NetlistSpiceWriter())

netlist2 = kdb.Netlist()
circ = kdb.Circuit()
circ.name = "test2"
netlist2.add(circ)
found_one = netlist1.circuit_by_name("test1")
netlist2.add(found_one)
netlist2.write("test2.cir", kdb.NetlistSpiceWriter())