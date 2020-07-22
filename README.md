# Reconstructing scenes for OpenVR headsets

This repository allows you to use OpenVR headsets to create 3D reconstructions, or to position 3D reconstructions using other cameras.

openvr_camera.py takes pictures using an OpenVR headset and stores to positional data of each picture in a format that COLMAP accepts.

reconstruct.py uses COLMAP functions to recoonstruct a scene, using the positioning data captured in openvr_camera.py or not.

## Requirements:
Python >=3.7 (might work with lesser versions but not tested)
requirements.txt details the required installs for using the python scripts

[COLMAP](https://colmap.github.io/index.html) is required for the reconstruction. Note that COLMAP requires CUDA for dense reconstruction, and so extra steps are required if a non-Nvidia card is used (instructions on the COLMAP FAQ).

## Usage

openvr_camera.py [-h] [--nimages NIMAGES] --save_dir SAVE_DIR
                 [--delay_between_images DELAY_BETWEEN_IMAGES]

--nimages controls how many images to take  
--delay_between_images controls how long between each image is taken  
--save_dir where is the images and other data saved

reconstruct.py [-h] --colmap COLMAP [--dataset_path DATASET_PATH]
               [--reference_geo_reg REFERENCE_GEO_REG]

--colmap where is COLMAP located (COLMAP.bat on Windows, COLMAP.sh on Linux)  
--dataset_path is where the images are located, where the images are located in DATASET_PATH/images/  
--reference_geo_reg is a seperate dataset to use as reference to scale, position and orientate this reconstruction. It expects REFERENCE_GEO_REG/images/ to contain images and REFERENCE_GEO_REG/geo_regis.txt to store the position of these images.  

reconstruct.py will output 3 .ply files in DATASET_PATH/dense/  
fused.ply is a dense point cloud  
delaunay.ply is an untextured mesh  
poisson.ply is a textured mesh and most likely the model you would want to use.  

To import poisson.ply to a 3D VR rendering engine you must convert it to another format. For this [MeshLab](https://www.meshlab.net/) can be used. The .ply file can be straight imported (File->Import Mesh) into MeshLab and exported (File->Export Mesh As, select .obj on file type drop down) to an .obj file that can be imported into a VR rendering engine but this won't have the colour information. To do this:

Create parameterization: Filters->Texture->Parameretization Trivial Per-Triangle

You'll probably need to bump up the Texture Dimension for this to work, but try to keep it under 8192 if you're using Unity as Unity has a max size on textures of 8192px and it can look really weird if you're texture file is over that. If you get the error Inter-triangle border is too much, increase the texture dimension

Transfer colour to file: Filters->Texture->Transfer: Vertex Color to Texture

Input the width and height as the size of the texture that you inputed for the last step. Tick the Assign texture box, click apply and then wait as it might take a while. 

Export as .obj, make sure that TexCoord is ticked in the export settings, and you should be able import the .obj and the .png texture into your VR rendering engine of choice and enjoy your scene.
