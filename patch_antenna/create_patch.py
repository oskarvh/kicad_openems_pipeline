"""
Script that creates a patch antenna. 

If no PCB files are found, then a patch is created from the 
submodule in this dir. 
"""
# Standard libs
import os
import tempfile
import json
import shutil
import sys
from typing import Any, Optional

# Extended libs
import pcbnew
from CSXCAD  import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import *
from gerber2ems.simulation import Simulation
from gerber2ems.postprocess import Postprocesor
from gerber2ems.config import Config
import gerber2ems.importer as importer

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
    # Set netclass:
    gnd_plane.SetNet("GND")
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

    # Add the simulation port
    footprint = pcbnew.FOOTPRINT(pcb)
    footprint.SetReference("SP1")   # Simulation ports must be SP_xxx
    # Set the reference to the end of the feedline
    sp1_y = feedline_start_y
    sp1_x = center_x_mm
    # Set the reference (silk layer) relative to the footprint
    footprint.Reference().SetPos(pcbnew.VECTOR2I_MM(0,-2))
    footprint.SetExcludedFromPosFiles(False)
    footprint.SetValue("Simulation_Port")
    pcb.Add(footprint)# add it to our pcb
    mod_pos = pcbnew.VECTOR2I_MM(sp1_x,sp1_y)
    footprint.SetPosition(mod_pos)



def fromUTF8Text( afilename ):
    if sys.version_info < (3, 0):
        return afilename.encode()
    else:
        return afilename

def export_gerbers(kicad_pcb_filename, output_dir, stackup_filename, project_name):
    """
    Function to export gerber files from KiCAD pcbNew board.
    
    :param pcb: <pcbnew.BOARD> Board object to be exported
    :param output_dir: <str> String pointing to where the files should be exported. 
    """
    # In order to get the naming convention correct, we need to open 
    # the board from source:
    pcb = pcbnew.LoadBoard(kicad_pcb_filename)

    # Create the plot controller object based of the pcb, and get the plot options
    plot_controller = pcbnew.PLOT_CONTROLLER(pcb)
    plot_options = plot_controller.GetPlotOptions()

    # Set the output directory based on the argument
    plot_options.SetOutputDirectory(output_dir)

    # Set some important plot options (see pcb_plot_params.h):
    plot_options.SetPlotFrameRef(False)     #do not change it
    plot_options.SetSketchPadLineWidth(pcbnew.FromMM(0.1))

    plot_options.SetAutoScale(False)        #do not change it
    plot_options.SetScale(1)                #do not change it
    plot_options.SetMirror(False)
    plot_options.SetUseGerberAttributes(True)
    plot_options.SetIncludeGerberNetlistInfo(True)
    plot_options.SetUseGerberProtelExtensions(False)
    plot_options.SetUseAuxOrigin(True)

    # This by gerbers only
    plot_options.SetSubtractMaskFromSilk(False)
    # Disable plot pad holes
    plot_options.SetDrillMarksType( pcbnew.DRILL_MARKS_NO_DRILL_SHAPE )

    # Skip plot pad NPTH when possible: when drill size and shape == pad size and shape
    # usually sel to True for copper layers
    plot_options.SetSkipPlotNPTH_Pads( False )
    

    # Create a plot plan, and export
    with open(stackup_filename, "r", encoding="utf-8") as file:
        try:
            stackup_config = json.load(file)
        except json.JSONDecodeError as error:
            raise json.JSONDecodeError(f"JSON decoding of stackup failed at {error.lineno}:{error.colno}: {error.msg,}")

    for layer in stackup_config["layers"]:
        # Fetch the KiCAD layer definiton, if the layer is defined
        if "kicad_layer" in layer:
            kicad_layer = getattr(pcbnew, layer["kicad_layer"])
            if kicad_layer <= pcbnew.B_Cu:
                plot_options.SetSkipPlotNPTH_Pads( True )
            else:
                plot_options.SetSkipPlotNPTH_Pads( False )
            name_suffix = layer["name"]
            plot_controller.SetLayer(kicad_layer)
            plot_controller.OpenPlotfile(
                name_suffix,
                pcbnew.PLOT_FORMAT_GERBER,
            )
            plot_controller.PlotLayer()
            #print( 'plot %s' % fromUTF8Text( plot_controller.GetPlotFileName() ) )

    drlwriter = pcbnew.EXCELLON_WRITER(pcb)
    drlwriter.SetMapFileFormat(pcbnew.PLOT_FORMAT_PDF)

    mirror = False
    minimalHeader = False
    offset = pcbnew.VECTOR2I(0,0)
    # False to generate 2 separate drill files (one for plated holes, one for non plated holes)
    # True to generate only one drill file
    mergeNPTH = False
    drlwriter.SetOptions( mirror, minimalHeader, offset, mergeNPTH )

    metricFmt = True
    drlwriter.SetFormat( metricFmt )

    genDrl = True
    genMap = True
    #print( 'create drill and map files in %s' % fromUTF8Text( plot_controller.GetPlotFileName() ) )
    drlwriter.CreateDrillandMapFilesSet( plot_controller.GetPlotDirName(), genDrl, genMap )


    plot_controller.ClosePlot()

def export_pos(kicad_pcb_filename, csv_filename):
    """
    Function to export the position file. 
    """
    # Load the board from the filename
    pcb = pcbnew.LoadBoard(kicad_pcb_filename)
    plot_exporter = pcbnew.PLACE_FILE_EXPORTER(
        aBoard = pcb, 
        aUnitsMM = True, # Use mm as units
        aOnlySMD = False, # Export more than SMD
        aExcludeAllTH = False, # Don't exclude TH
        aExcludeDNP = False, # Exlude DNP (do not place) components
        aTopSide= True, # Export top side components
        aBottomSide= True, # Export bottom side components
        aFormatCSV=True, # Export as .csv
        aUseAuxOrigin= True, # Aux origin used for gerbers as well
        aNegateBottomX=False, # Do not use negative x on bottom layer
    )
    # Generate file:
    print(f"{plot_exporter.GenPositionData()=}")
    # GenPositionData gives the csv file as a string
    pos_data = plot_exporter.GenPositionData()
    # Condition the string to look more like a csv file.
    pos_data = pos_data.splitlines()
    with open(csv_filename, "w") as f:
        for line in pos_data:
            if line.startswith("#"):
                continue
            f.write(line.replace("\t", ",") + "\n")
    
    
    
    

def create_dir(path: str, cleanup: bool = False) -> None:
    """
    Creates a directory if it doesn't exist
    WARNING: IF CLEANUP=TRUE THEN IT WILL DELETE
    THE BRANCHES OF PATH, SEE DOCUMENTATION 
    FOR shutil.rmtree BEFORE USING! 

    :param path: <str> absolute path to dir
    :param cleanup: <bool> 
    """
    directory_path = os.path.join(os.getcwd(), path)
    if cleanup and os.path.exists(directory_path):
        shutil.rmtree(directory_path)
    if not os.path.exists(directory_path):
        os.mkdir(directory_path)


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
    pcb_dir = os.path.dirname(os.path.abspath(__file__)) + "/kicad/"
    # Create the dir if it doesn't exist:
    if not os.path.exists(pcb_dir):
        os.makedirs(pcb_dir)
    kicad_pcb_filename = pcb_dir + "patch_antenna.kicad_pcb"
    print(f"Saving board to {kicad_pcb_filename}")
    pcbnew.SaveBoard(
        aFileName = kicad_pcb_filename, 
        aBoard = pcb,
    )

    # Export the gerber:
    gerber_dir = os.path.dirname(os.path.abspath(__file__)) + "/fab"
    # Create the dir if it doesn't exist:
    if not os.path.exists(gerber_dir):
        os.makedirs(gerber_dir)
    stackup_file = gerber_dir + "/stackup.json"
    export_gerbers(kicad_pcb_filename, gerber_dir, stackup_file, "patch_antenna")
    pos_filename = gerber_dir + "/patch_antenna-pos.csv"
    export_pos(kicad_pcb_filename, pos_filename)

    # Open and parse the config:
    config_filename = gerber_dir + "/config.json"
    with open(config_filename, "r", encoding="utf-8") as file:
        try:
            config = json.load(file)
        except json.JSONDecodeError as error:
            print(f"JSON decoding failed at {error.lineno}:{error.colno}: {error.msg,}")
            return
        
    # Create the gerber2ems config based on the config read from the json file
    # Set the args parameter to None for now. 
    class dummyArgs:
        pass
    args_dummy = dummyArgs()
    setattr(args_dummy, "debug", False)
    setattr(args_dummy, "export_field", True)
    gerber2ems_config = Config(config, args_dummy)
    # Overide the configs default directories:
    
    ems_base_dir = os.path.dirname(os.path.abspath(__file__)) + "/ems/"
    geometry_dir = ems_base_dir + "geometry/"
    sim_dir = ems_base_dir + "sim/"
    result_dir = ems_base_dir + "results/"
    create_dir(ems_base_dir, cleanup=False)
    create_dir(geometry_dir, cleanup=True)
    create_dir(sim_dir, cleanup=True)
    create_dir(result_dir, cleanup=True)
    gerber2ems_config.base_dir = ems_base_dir
    gerber2ems_config.geometry_dir = geometry_dir
    gerber2ems_config.simulation_dir = sim_dir
    gerber2ems_config.results_dir = result_dir
    gerber2ems_config.fab_dir = gerber_dir
    sim = Simulation()
    # Get the stackup filename. Located parallell to this file.
    
    importer.import_stackup()
    importer.process_gbrs_to_pngs()
    
    top_layer_name = Config.get().get_metals()[0].file
    (width, height) = importer.get_dimensions(top_layer_name + ".png")
    Config.get().pcb_height = height
    Config.get().pcb_width = width

    sim.create_materials()
    sim.add_gerbers()
    sim.add_mesh()
    sim.add_substrates()
    if Config.get().arguments.export_field:
        sim.add_dump_boxes()
    sim.set_boundary_conditions(pml=False)
    sim.add_vias()
    # Add the ports
    sim.ports = []
    importer.import_port_positions()
    for index, port_config in enumerate(Config.get().ports):
        sim.add_msl_port(port_config, index, index == None)
    sim.save_geometry()

    print("Running simulation")
    
    # Start with a single thread. 
    # TODO: Get this from the config later on..
    simulate(threads=8) 

    print("Postprocessing")
    
    sim = Simulation()
    postprocess(sim)

def add_ports(sim: Simulation, excited_port_number: Optional[int] = None) -> None:
    """Add ports for simulation."""
    #logger.info("Adding ports")

    sim.ports = []
    importer.import_port_positions()

    for index, port_config in enumerate(Config.get().ports):
        sim.add_msl_port(port_config, index, index == excited_port_number)

def simulate(threads: None | int = None) -> None:
    """Run the simulation."""
    for index, port in enumerate(Config.get().ports):
        if port.excite:
            sim = Simulation()
            importer.import_stackup()
            sim.create_materials()
            sim.set_excitation()
            #logging.info("Simulating with excitation on port #%i", index)
            sim.load_geometry()
            add_ports(sim, index)
            sim.run(index, threads=threads)

def add_virtual_ports(sim: Simulation) -> None:
    """Add virtual ports needed for data postprocessing due to openEMS api design."""
    print("Adding virtual ports")
    for port_config in Config.get().ports:
        sim.add_virtual_port(port_config)

def postprocess(sim: Simulation) -> None:
    """Postprocess data from the simulation."""
    if len(sim.ports) == 0:
        add_virtual_ports(sim)

    frequencies = np.linspace(Config.get().start_frequency, Config.get().stop_frequency, 1001)
    post = Postprocesor(frequencies, len(Config.get().ports))
    impedances = np.array([p.impedance for p in Config.get().ports])
    post.add_impedances(impedances)

    for index, port in enumerate(Config.get().ports):
        if port.excite:
            reflected, incident = sim.get_port_parameters(index, frequencies)
            for i, _ in enumerate(Config.get().ports):
                post.add_port_data(i, index, incident[i], reflected[i])

    post.process_data()
    post.save_to_file()
    post.render_s_params()
    post.render_impedance()
    post.render_smith()
    post.render_diff_pair_s_params()
    post.render_diff_impedance()
    post.render_trace_delays()

if __name__ == "__main__":
    main()