#!/bin/env python
import argparse
import os
import sys
import time
from pathlib import Path
import ctypes

import openvr
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image
from scipy.spatial.transform import Rotation

from database import COLMAPDatabase
from read_write_model import qvec2rotmat, rotmat2qvec, Camera, CAMERA_MODEL_NAMES
import read_write_model
from reconstruct import ColmapFolder

def hmd_matrix_to_numpy(hmd_matrix):
  pose_arr = np.zeros((4, 4))

  pose_arr[0] = hmd_matrix[0]
  pose_arr[1] = hmd_matrix[1]
  pose_arr[2] = hmd_matrix[2]
  pose_arr[3] = [0, 0, 0, 1]
  return pose_arr

def draw_axes(ax, transform_mat, **kwargs):
  axis = np.zeros((3, 4))

  axis[0] = transform_mat @ np.array([1, 0, 0, 0]).T
  axis[1] = transform_mat @ np.array([0, 1, 0, 0]).T
  axis[2] = transform_mat @ np.array([0, 0, 1, 0]).T
  pos     = transform_mat @ np.array([0, 0, 0, 1]).T

  ax.quiver(pos[0], pos[2], pos[1], axis[:, 0], axis[:, 2], axis[:, 1], normalize=True, length=0.15, colors=['r', 'g', 'b', 'r', 'r', 'g', 'g', 'b', 'b'])

def take_steamvr_images(save_dir, num_images, delay_between_images):
  plt.show()

  openvr.init(openvr.VRApplication_Scene)

  convert_coordinate_system = np.identity(4)
  convert_coordinate_system[:3, :3] = Rotation.from_euler('XYZ',(180, 0, 0), degrees=True).as_matrix()

  device = openvr.k_unTrackedDeviceIndex_Hmd

  num_cameras = openvr.VRSystem().getInt32TrackedDeviceProperty(device, openvr.Prop_NumCameras_Int32)

  camera_to_head_mat = (openvr.HmdMatrix34_t*num_cameras) ()

  openvr.VRSystem().getArrayTrackedDeviceProperty(device, openvr.Prop_CameraToHeadTransforms_Matrix34_Array, openvr.k_unHmdMatrix34PropertyTag, camera_to_head_mat, 48*num_cameras)

  cam = openvr.VRTrackedCamera()

  cam_handle = cam.acquireVideoStreamingService(device)

  width, height, buffer_size = cam.getCameraFrameSize(device, openvr.VRTrackedCameraFrameType_MaximumUndistorted)

  fig = plt.figure()
  ax = fig.add_subplot(111, projection='3d')
  ax.set_xlabel('x axis - metres')
  ax.set_ylabel('z axis - metres')
  ax.set_zlabel('y axis - metres')
  ax.set_xlim(-0.5, 0.5)
  ax.set_ylim(-0.5, 0.5)
  ax.set_zlim(0, 1)

  save_dir = ColmapFolder(save_dir)

  db = COLMAPDatabase.connect(save_dir.database_path)
  db.create_tables()

  init_params = np.array((420.000000, (width/num_cameras)/2, height/2, 0.000000))

  camera_model = CAMERA_MODEL_NAMES['SIMPLE_RADIAL']

  cameras = {}
  camera_to_head_transforms = {}

  for i in range(num_cameras):
    cam_id = db.add_camera(camera_model.model_id, width/2, height, init_params)
    camera_to_head_transforms[cam_id] = hmd_matrix_to_numpy(camera_to_head_mat[i])
    cameras[cam_id] = Camera(id=cam_id, model=camera_model.model_name, width=width/num_cameras, height=height, params=init_params)

  poses = []  # Let waitGetPoses populate the poses structure the first time
  cam_positions = []

  images = []

  for i in range(num_images):

    poses, game_poses = openvr.VRCompositor().waitGetPoses(poses, None)
    hmd_pose = poses[openvr.k_unTrackedDeviceIndex_Hmd]

    if not hmd_pose.bPoseIsValid:
      print("Pose not valid")
      continue

    world_to_head = hmd_matrix_to_numpy(hmd_pose.mDeviceToAbsoluteTracking)

    world_to_cams = {id_:world_to_head @ head_to_cam @ convert_coordinate_system for (id_,head_to_cam) in camera_to_head_transforms.items()}

    image_buffer = (ctypes.c_ubyte * buffer_size)()
    try:
      cam.getVideoStreamFrameBuffer(cam_handle, openvr.VRTrackedCameraFrameType_MaximumUndistorted, image_buffer, buffer_size)
    except:
      print("Error getting video stream buffer")
      continue

    image_array = np.array(image_buffer)

    image_array = image_array.reshape((height, width, 4))

    image_array = image_array[:, :, 0:3]

    image_array = np.clip(image_array, 0, 255)

    for j, (cam_id, world_to_cam) in enumerate(world_to_cams.items()):
      image = Image.fromarray(image_array[:, int(width/num_cameras)*j:int(width/num_cameras)*(j+1), :])

      name = f"{i:03d}_cam{j}.jpg"

      image.save(save_dir.images_path / name)

      image_obj = read_write_model.Image(camera_id=cam_id, name=name, transformation_matrix=world_to_cam)

      images.append(image_obj)

      draw_axes(ax, transform_mat=world_to_cam)

    fig.show()

    fig.canvas.draw()
    fig.canvas.flush_events()
    time.sleep(delay_between_images)
    print(f"Picture taken :{i}")

  image_dict = {}

  print("All pictures taken")

  with open(save_dir.geo_reg_path, 'w') as geo_reg_file:

    for image in images:
      image_id = db.add_image(image=image)
      image.id = image_id
      image_dict[image_id] = image
      geo_reg_file.write(f"{name} {' '.join(map(str, image.transformation_matrix[0:3, 3]))}\n")

  read_write_model.write_model(cameras, image_dict, {}, save_dir.sparse_path, '.txt')

  db.commit()
  db.close()

  print("Metadata saved")

  openvr.shutdown()
  plt.show()

if __name__ == "__main__":
  parser = argparse.ArgumentParser()

  parser.add_argument("--nimages", type=int, default=25)
  parser.add_argument("--save_dir", required=True)
  parser.add_argument("--delay_between_images", type=int, default=0.5)

  args = parser.parse_args()

  take_steamvr_images(save_dir=args.save_dir, num_images=args.nimages, delay_between_images=args.delay_between_images)