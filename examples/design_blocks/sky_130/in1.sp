
* cell in1
.SUBCKT in1
* net 1 D
* net 2 S
* cell instance p_mos r0 *1 0,0
Xp_mos 1 2 p_mos
* cell instance n_mos r0 *1 0,0
Xn_mos 3 4 n_mos
.ENDS in1

* cell n_mos
* pin D
* pin S
.SUBCKT n_mos 1 2
.ENDS n_mos

* cell p_mos
* pin D
* pin S
.SUBCKT p_mos 1 2
* net 1 D
* net 2 S
.ENDS p_mos
