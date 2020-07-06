from pathlib import Path, PurePath
import subprocess
import sys
import os
import shutil

import read_write_model

class ColmapDelegator:
  """Wrapper for calling colmap functions""" 
  commands = [
    'feature_extractor',
    'exhaustive_matcher',
    'mapper',
    'model_aligner',
    'image_undistorter',
    'patch_match_stereo',
    'stereo_fusion',
    'poisson_mesher',
    'delaunay_mesher',
  ]

  def __init__(self, colmap_call):
    self.colmap_call = colmap_call

  def __getattr__(self, name):
    if name in self.commands:
      return self.call_colmap_command_curry(name)

  def call_colmap_command(self, function, **kwargs):
    return self.call_colmap_command_curry(function)(**kwargs)

  def call_colmap_command_curry(self, function):
    def helper(**kwargs):
      command = [self.colmap_call]
      command.append(str(function))
      for arg_key, arg_val in kwargs.items():
        command.append(f'--{arg_key}')
        command.append(str(arg_val))

      subprocess.call(command, stdout=sys.stdout, stderr=subprocess.STDOUT)
    
    return helper

class ColmapFolder:
  """Used to interact with the typical COLMAP folder structure"""

  def __init__(self, path):
    self.path = Path(path)
    if not self.path.exists():
      os.mkdir(self.path)
    if not self.workspace_path.exists():
      os.mkdir(self.workspace_path)
    if not self.sparse_path.exists():
      os.mkdir(self.sparse_path)
    if not self.images_path.exists():
      os.mkdir(self.images_path)
  
  @property
  def dataset_path(self):
    return self.path

  @property
  def workspace_path(self):
    return self.dataset_path / 'dense'
  
  @property
  def fused_path(self):
    return self.workspace_path / 'fused.ply'
  
  @property
  def poisson_path(self):
    return self.workspace_path / 'poisson.ply'
  
  @property
  def delaunay_path(self):
    return self.workspace_path / 'delaunay.ply'
  
  @property
  def images_path(self):
    return self.dataset_path / 'images'
  
  @property
  def sparse_path(self):
    return self.dataset_path / 'sparse2'
  
  @property
  def database_path(self):
    return self.dataset_path / 'database.db'
  
  @property
  def geo_reg_path(self):
    return self.dataset_path / 'geo_regis.txt'

class Reconstruct:
  """Used to reconstruct scenes"""
  def __init__(self, delegate, folder):
    self.delegate = delegate
    self.folder = folder

  def auto_reconstruct(self, reference_reconstruct=None):
    if reference_reconstruct is not None:

      if not (self.folder.path / 'combined').exists():      
        shutil.copytree(reference_reconstruct.path, self.folder.path / 'combined')
        
        combined_reconstruct_folder = ColmapFolder(self.folder.path / 'combined')

        images = os.listdir(self.folder.images_path)
        
        for image in images:
          shutil.copy2(self.folder.images_path / image, combined_reconstruct_folder.images_path)

      combined_reconstruct_folder = ColmapFolder(self.folder.path / 'combined')
      combined_reconstruct = Reconstruct(self.delegate, combined_reconstruct_folder)
      combined_reconstruct.sparse_reconstruct()
      
      _, comb_images, _ = read_write_model.read_model(combined_reconstruct_folder.sparse_path / '0', '.bin')

      with self.folder.geo_reg_path.open('w') as f:
        for image in comb_images.values():
          if image.name in images:
            f.write(f"{image.name} {' '.join(map(str, image.transformation_matrix[0:3, 3]))}\n")
    
    self.sparse_reconstruct()
    self.dense_reconstruct()

  def sparse_reconstruct(self):
    """Reconstructs a small number of points and positions cameras in 3D space"""
    self.delegate.feature_extractor(database_path=self.folder.database_path, image_path=self.folder.images_path)
    self.delegate.exhaustive_matcher(database_path=self.folder.database_path)
    self.delegate.mapper(database_path=self.folder.database_path, image_path=self.folder.images_path, output_path=self.folder.sparse_path)
    
    if self.folder.geo_reg_path.exists():
      self.delegate.model_aligner(input_path=self.folder.sparse_path/'0', output_path=self.folder.sparse_path/'0', ref_images_path=self.folder.geo_reg_path, robust_alignment=0)

  def dense_reconstruct(self):
    """Takes positions of cameras and images to create full 3D models"""
    self.delegate.image_undistorter(image_path=self.folder.images_path, input_path=self.folder.sparse_path/'0', output_path=self.folder.workspace_path, max_image_size=2000)
    self.delegate.patch_match_stereo(workspace_path=self.folder.workspace_path)
    self.delegate.stereo_fusion(workspace_path=self.folder.workspace_path, output_path=self.folder.fused_path)
    self.delegate.poisson_mesher(output_path=self.folder.poisson_path, input_path=self.folder.fused_path)
    self.delegate.delaunay_mesher(output_path=self.folder.delaunay_path, input_path=self.folder.workspace_path)

  def reconstruct_after_inpaint(self):
    self.delegate.stereo_fusion(workspace_path=self.folder.workspace_path, output_path=self.folder.fused_path)
    self.delegate.poisson_mesher(output_path=self.folder.poisson_path, input_path=self.folder.fused_path)
    self.delegate.delaunay_mesher(output_path=self.folder.delaunay_path, input_path=self.folder.workspace_path)

if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument("--colmap", required=True)
  parser.add_argument("--dataset_path", type=str, default="./")
  parser.add_argument("--reference_geo_reg", type=str, default=None)

  args = parser.parse_args()

  deleg = ColmapDelegator(args.colmap)

  folder = ColmapFolder(args.dataset_path)

  recon = Reconstruct(deleg, folder)

  if args.reference_geo_reg is not None:
    reference_reconstruct = ColmapFolder(args.reference_geo_reg)
  else:
    reference_reconstruct = None 

  recon.auto_reconstruct(reference_reconstruct=reference_reconstruct)