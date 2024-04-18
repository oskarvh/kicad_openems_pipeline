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

from patch_antenna_calculator.patch_antenna_calculator import (
    substrate,
    patch_antenna,
)

freq = np.linspace(2000e6, 3000e6, 101)
ref_freq = 2450e6 # 2.45 GHz
unit = 1e-3
sim = Simulation(freq=freq, unit=unit, reference_frequency=ref_freq)

pcb_prop = common_pcbs["jlcpcb2"]

# Define and calculate the substrate
print(f"{pcb_prop.substrate_thickness(index=0)=}")
s = substrate(
    e_r = pcb_prop.substrate.epsr_at_freq(2.4e9), # Dielectric constant
    height_mm = pcb_prop.substrate_thickness(index=0), # dielectric thickness in mm
    cu_thickness_um = pcb_prop.copper_thickness(index=0, unit=1/1000), # Copper thickness in um
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
pcb = PCB(
    sim=sim, 
    pcb_prop=pcb_prop,
    width = antenna.w, 
    length=antenna.l,
    layers=range(3), # cu/substrate/cu
    omit_copper=[0], # Do not fill layer 0/top with gnd copper
)

# Create the polygon
# HACK: Testing.
coords = [
    Coordinate2(0,0),
    Coordinate2(0,1),
    Coordinate2(1,1),
    Coordinate2(1,0),
]
p = MetalPolygon(
    pcb = pcb, 
    coordinates=coords, 
    position=Coordinate2(0,0)
)