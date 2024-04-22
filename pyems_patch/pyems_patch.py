"""
Written by Oskar von Heideken
2024

Script that uses pyems to simulate a patch antenna. 
"""

import numpy as np
from pyems.structure import Microstrip, PCB, MicrostripCoupler, MetalPolygon
from pyems.simulation import Simulation
from pyems.pcb import common_pcbs
from pyems.calc import phase_shift_length, microstrip_effective_dielectric
from pyems.utilities import print_table
from pyems.coordinate import Coordinate2, Axis, Box3, Coordinate3
from pyems.mesh import Mesh
from pyems.field_dump import FieldDump, DumpType
from pyems.kicad import write_footprint

from matplotlib import pyplot as plt

from patch_antenna_calculator.patch_antenna_calculator import (
    substrate,
    patch_antenna,
)

freq = np.linspace(2000e6, 3000e6, 101)
ref_freq = 2450e6 # 2.45 GHz
unit = 1e-3
sim = Simulation(freq=freq, unit=unit, reference_frequency=ref_freq)

pcb_prop = common_pcbs["jlcpcb2"]

# Define and calculate the substrate for the antenna
s = substrate(
    e_r = pcb_prop.substrate.epsr_at_freq(2.4e9), # Dielectric constant
    height_mm = pcb_prop.substrate_thickness(index=0, unit=1e-3), # dielectric thickness in mm
    cu_thickness_um = pcb_prop.copper_thickness(index=0, unit=1e-6), # Copper thickness in um
)

# Calculate the antenna dimensions
antenna = patch_antenna(
    substrate = s, 
    frequency_hz = ref_freq,
)
antenna.calculate_antenna_params()

# Compare the e_eff calculations just for fun
antenna_calc_e_eff = antenna.calculate_epsilon_eff(antenna.w)
pyems_e_eff = microstrip_effective_dielectric(
    pcb_prop.substrate.epsr_at_freq(ref_freq),
    substrate_height=pcb_prop.substrate_thickness(0, unit=1),
    trace_width=float(antenna.w),
)
print(f"My calculation of e_eff: {antenna_calc_e_eff}")
print(f"PyEMS calculation of e_eff: {pyems_e_eff}")

# Define the PCB based on the outline of the calculated antenna
# This is the basis of the simulation structure. 
substrate_width = round(antenna.ground_plane_length*1.1/unit)
substrate_length = round(antenna.ground_plane_width*1.1/unit)

pcb = PCB(
    sim=sim, 
    pcb_prop=pcb_prop,
    width = substrate_width,
    length = substrate_length,
    layers=range(3), # cu/substrate/cu
    omit_copper=[0], # Do not fill layer 0/top with gnd copper
)

# Create the polygon
antenna_inset_coord= (0,round(-antenna.l/(2*unit),2))
antenna_coords = antenna.export_coordinates(unit=unit, starting_coord=antenna_inset_coord)
coords = []
x_pts = []
y_pts = []
for x,y in antenna_coords:
    coords.append(Coordinate2(round(x,3),round(y,3)))
    x_pts.append(x)
    y_pts.append(y)
# plt.plot(x_pts, y_pts)
# plt.grid()
# plt.show()


p = MetalPolygon(
    pcb = pcb, 
    coordinates=coords, 
    position=coords[0]
)

# Add a microstrip line as a feed and port
antenna_x, antenna_y = antenna_inset_coord
tl_length = round((antenna.ground_plane_length/unit - antenna.l/unit)/2, 3)
tl_center = Coordinate2(antenna_x, antenna_y-tl_length/2)

Microstrip(
    pcb=pcb,
    position=tl_center,
    length=tl_length,
    width=round(antenna.feed_line_w/unit, 3),
    propagation_axis=Axis("y"),
    port_number=1,
    excite=True,
    ref_impedance=50,
)


# Create the mesh
# Mesh(
#     sim=sim,
#     metal_res=1 / 10,
#     nonmetal_res=1 / 10,
#     smooth=(1.1, 1.5, 1.5),
#     min_lines=3,
#     expand_bounds=((0, 0), (0, 0), (10, 10)),
# )
Mesh(
    sim=sim,
    metal_res=1 / 20,
    nonmetal_res=1 / 10,
    min_lines=5,
    expand_bounds=((10, 10), (10, 10), (10, 10)),
)

sim.run()

print_table(
    data=[sim.freq / 1e9, np.abs(sim.ports[0].impedance()), sim.s_param(1, 1)],
    col_names=["freq", "z0", "s11"],
    prec=[2, 4, 4],
)