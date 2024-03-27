# kicad_openems_pipeline
Attempting to create a pipeline for RF projects using KiCAD and OpenEMS

# Install dependencies
These are the dependencies I have. 

- Kicad 8
- OpenEMS v.0.0.36 (Installed from https://docs.openems.de/install.html#linux, with python interface). 

For OpenEMS, remember to also update the underlying Python packages, such as Numpy, Matplotlib and more. 

- Install this repos submodules (`git submodule update --recursive`)

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
