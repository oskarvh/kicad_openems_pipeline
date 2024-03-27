"""
Script that creates a patch antenna. 

If no PCB files are found, then a patch is created from the 
submodule in this dir. 
"""
# Standard libs
import os
import tempfile

# Extended libs
import pcbnew
from CSXCAD  import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import *
import gerber2ems

Sim_Path = os.path.join(tempfile.gettempdir(), 'Simp_Patch')

# Modules from this repo
from patch_antenna_calculator.patch_antenna_calculator import (
    substrate,
    patch_antenna,
)

def create_kicad_board(antenna, pcb, center_x_mm, center_y_mm):
    """
    Function to transfer the antenna parameters to 
    a kicad board file. 

    :param antenna: <patch_antenna_calculator.patch_antenna> Calculated patch antenna
    :param pcb: <pcbnew board object> KiCAD PCB board object
    :param center_x_mm: <int> X coordinate for center of board in mm 
    :param center_y_mm: <int> Y coordinate for center of board in mm 
    :return: <pcbnew board object> Resulting PCB object.
    """
     # The calculated width is the side where the feed line enters. 
    # If we then have the feed line on the bottom, length = Y, Width = X 
    # Create a board outline, based on the patch_antenna.ground_plane_[length/width]
    outline = pcbnew.PCB_SHAPE(pcb)
    outline.SetShape(pcbnew.SHAPE_T_RECT)
    outline.SetFilled(False)
    outline.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
    outline.SetStart(
        pcbnew.VECTOR2I_MM(
            center_x_mm - antenna.ground_plane_width/2, 
            center_y_mm - antenna.ground_plane_length/2,
        )
    )
    outline.SetEnd(
        pcbnew.VECTOR2I_MM(
            center_x_mm + antenna.ground_plane_width/2, 
            center_y_mm + antenna.ground_plane_length/2,
        )
    )
    outline.SetLayer(pcbnew.Edge_Cuts)
    outline.SetWidth(pcbnew.FromMM(0.1))
    pcb.Add(outline)

    # Add the ground plane on the secondary side:
    gnd_plane = pcbnew.PCB_SHAPE(pcb)
    gnd_plane.SetShape(pcbnew.SHAPE_T_RECT)
    gnd_plane.SetFilled(True)
    gnd_plane.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
    gnd_plane.SetStart(
        pcbnew.VECTOR2I_MM(
            center_x_mm - antenna.ground_plane_width/2, 
            center_y_mm - antenna.ground_plane_length/2,
        )
    )
    gnd_plane.SetEnd(
        pcbnew.VECTOR2I_MM(
            center_x_mm + antenna.ground_plane_width/2, 
            center_y_mm + antenna.ground_plane_length/2,
        )
    )
    gnd_plane.SetLayer(pcbnew.B_Cu)
    pcb.Add(gnd_plane)

    # Create the patch on the top. 
    # This is a rectangular patch with inset. 
    # points(x,y) of the patch
    pts = [
        # Start in top left corner
        (center_x_mm - antenna.w/2, center_y_mm - antenna.l/2),
        # Go down
        (center_x_mm - antenna.w/2, center_y_mm + antenna.l/2),
        # Go in towards feedline, but stop before feedline width/2 + spacing
        (center_x_mm - antenna.feed_line_w/2 - antenna.feed_line_clearance, 
            center_y_mm + antenna.l/2),
        # Go up to create the left side of the inset feed clearance:
        (center_x_mm - antenna.feed_line_w/2 - antenna.feed_line_clearance, 
            center_y_mm + antenna.l/2 - antenna.feed_line_l),
        # Go to the right, and create the clearance
        (center_x_mm + antenna.feed_line_w/2 + antenna.feed_line_clearance, 
            center_y_mm + antenna.l/2 - antenna.feed_line_l),
        # Go down to the corner of the right side of the inset line
        (center_x_mm + antenna.feed_line_w/2 + antenna.feed_line_clearance, 
            center_y_mm + antenna.l/2),
        # Now go to the bottom right corner of the patch
        (center_x_mm + antenna.w/2, center_y_mm + antenna.l/2),
        # Go up to the top right corner
        (center_x_mm + antenna.w/2, center_y_mm - antenna.l/2),
        # And finish at the starting point
        (center_x_mm - antenna.w/2, center_y_mm - antenna.l/2),
    ]
    # Convert points from floats to vectors
    pts = [pcbnew.VECTOR2I_MM(x,y) for (x,y) in pts]

    sps = pcbnew.SHAPE_POLY_SET()
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for (x,y) in pts:
        chain.Append(x, y)
    chain.SetClosed(True)
    sps.AddOutline(chain)

    ps = pcbnew.PCB_SHAPE(pcb, pcbnew.SHAPE_T_POLY)
    ps.SetLayer(pcbnew.F_Cu)
    ps.SetPolyShape(sps)
    ps.SetFilled(True)

    pcb.Add(ps)

    # Add mask cutout for patch as well
    mask_margin_mm = 1
    patch_mask = pcbnew.PCB_SHAPE(pcb)
    patch_mask.SetShape(pcbnew.SHAPE_T_RECT)
    patch_mask.SetFilled(True)
    patch_mask.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
    patch_mask.SetStart(
        pcbnew.VECTOR2I_MM(
            center_x_mm - antenna.w/2 - mask_margin_mm, 
            center_y_mm - antenna.l/2 - mask_margin_mm,
        )
    )
    patch_mask.SetEnd(
        pcbnew.VECTOR2I_MM(
            center_x_mm + antenna.w/2 + mask_margin_mm, 
            center_y_mm + antenna.l/2 + mask_margin_mm,
        )
    )
    patch_mask.SetLayer(pcbnew.F_Mask)
    pcb.Add(patch_mask)

    # Add inset feed line. 
    # Calculate the start of the feedline, which is the bottom of the 
    # outline
    # Feed line also has got to account for the top layer clearance:
    top_layer_patch_clearance_y_mm = (antenna.ground_plane_length - antenna.l)/2
    feedline_start_y = center_y_mm + antenna.ground_plane_length/2
    # The x start coordinate of the feedline is the middle of the 
    # board, minus half the width of the feedline. 
    feedline_start_x = center_x_mm - antenna.feed_line_w/2
    
    # Add the feedline
    feedline = pcbnew.PCB_SHAPE(pcb)
    feedline.SetShape(pcbnew.SHAPE_T_RECT)
    feedline.SetFilled(True)
    feedline.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
    feedline.SetStart(
        pcbnew.VECTOR2I_MM(
            feedline_start_x, 
            feedline_start_y,
        )
    )
    feedline.SetEnd(
        pcbnew.VECTOR2I_MM(
            feedline_start_x + antenna.feed_line_w, 
            feedline_start_y - antenna.feed_line_l - top_layer_patch_clearance_y_mm,
        )
    )
    feedline.SetLayer(pcbnew.F_Cu)
    pcb.Add(feedline)

    # And finally, the mask cutout for the feedline:
    feedline_mask = pcbnew.PCB_SHAPE(pcb)
    feedline_mask.SetShape(pcbnew.SHAPE_T_RECT)
    feedline_mask.SetFilled(True)
    feedline_mask.SetPosition(pcbnew.VECTOR2I_MM(center_x_mm, center_y_mm))
    feedline_mask.SetStart(
        pcbnew.VECTOR2I_MM(
            feedline_start_x - mask_margin_mm, 
            feedline_start_y,
        )
    )
    feedline_mask.SetEnd(
        pcbnew.VECTOR2I_MM(
            feedline_start_x + antenna.feed_line_w + mask_margin_mm, 
            feedline_start_y - antenna.feed_line_l,
        )
    )
    feedline_mask.SetLayer(pcbnew.F_Mask)
    pcb.Add(feedline_mask)


def main():

    # Define and calculate the substrate
    s = substrate(
        e_r = 4.6, # Dielectric constant
        height_mm = 1.6, # dielectric thickness in mm
        cu_thickness_um = 35, # Copper thickness in um
    )
    center_frequency = 2.45e6

    # Calculate the antenna dimensions
    antenna = patch_antenna(
        substrate = s, 
        frequency_hz = center_frequency,
    )
    antenna.calculate_antenna_params()

    # Create an empty PCB
    pcb = pcbnew.CreateEmptyBoard()
    
    # Center coordinates
    center_x_mm = 100
    center_y_mm = 100

    # Convert the antenna params to the PCB object
    create_kicad_board(antenna, pcb, center_x_mm, center_y_mm)

    # Save the KiCAD board
    filename = os.path.dirname(os.path.abspath(__file__)) + "/kicad/patch_antenna.kicad_pcb"
    print(f"Saving board to {filename}")
    pcbnew.SaveBoard(
        aFileName = filename, 
        aBoard = pcb,
    )



if __name__ == "__main__":
    main()