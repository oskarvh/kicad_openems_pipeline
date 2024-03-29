# kicad_openems_pipeline
Attempting to create a pipeline for RF projects using KiCAD and OpenEMS


# 1. Install

These steps should make it possible to get this up and running. 

## 1.1. Clone this repo

Clone this repo
```
# Clone this repo:
git clone git@github.com:oskarvh/kicad_openems_pipeline.git

# cd into repo
cd kicad_openems_pipeline

# Update submodules 
git submodule update --recursive
```

## 1.2. Install dependencies

There are multiple dependencies for this repo. These are 
- Kicad 8
- OpenEMS v.0.0.36 (Installed from https://docs.openems.de/install.html#linux, with python interface). 

Moreover, the following dependencies are required (some might be covered by the OpenEMS install above). 
```
# Install OpenEMS deps
sudo apt-get install build-essential cmake git libhdf5-dev libvtk7-dev libboost-all-dev libcgal-dev libtinyxml-dev qtbase5-dev libvtk7-qt-dev

# Install deps for python interface
sudo pip install numpy matplotlib cython h5py

# Optional: Update pip in case stuff is outdated:
sudo python3 -m pip install --upgrade pip

# Install python deps:
sudo python3 -m pip install vtk scipy matplotlib h5py

# Install gerber2ems dependencies:
sudo apt install gerbv

# Optional, but nice:
sudo apt install paraview
```

## 1.3. Install gerber2ems
This project uses Antmicro's `gerber2ems` module to convert gerber files to a format that can be opened by OpenEMS. Assuming the submodules have been fetched, the package needs to be installed:
```
# cd into gerber2ems
cd <path to where you cloned the repo>/gerber2ems

# install the package
pip install .
```

## 1.2. Test install
A quick way to check that the installation worked is to run through the patch antenna generation and simulation, as that doesn't require any input: 

```
cd <path to where you cloned the repo>/kicad_openems_pipeline
python3 patch_antenna/create_patch.py
```

# Guide
See the writeup at aboutbytes.com for more details. Article not up yet, but will be at some point. 

# Background
RF electronics can be hard sometimes, especially if you don't have access to a simulator and you're trying to do some cool stuff. That's where this project comes in. 

I have been using Advanced Design Systems for a few years now, and it's great, but it's really very extremely expensive, so being a hobbyist using that program isn't really feasible. And I like open source tools, so here I want to combine KiCAD and OpenEMS into a pipeline for creating schematics and PCBs in a way such that I can improve my confidence level when it comes to RF design. 

Hence, this repo contains a few different RF designs, where the goal is to create the designs in KiCAD, simulate them in OpenEMS, order the design and measure the results to create a feedback loop. 

I hesistate using the word "one-stop-shop", because RF/EM simulation is quite an involved process and is highly dependent on the simulation paramters. 

In the future, other simulation methods other than OpenEMS might be used. 


## Starting point
The goal is to create and simulate the following designs:
- Patch antenna
- Microstrip transmission line
- Grounded Coplanar Waveguide (GCPW)
- GCPW with via

### Patch antenna
I've made another script to roughly calculate the antenna parameters for a two layer board, found here: https://github.com/oskarvh/patch_antenna_calculator. 

For convencience, that repo is imported into the `patch_antenna` as a submodule. This calculator is far from ideal, but I've found myself looking through old notes to create a similar patch over and over again, so this creates a nice baseline to work from. 

`python3 patch_antenna/create_patch.py` creates a KiCAD PCB file with a patch featuring an inset feedline calculated for 50 ohm (not guaranteed).

