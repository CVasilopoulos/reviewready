Fixes #1319

`vc_obj2tifxyz` was writing `meta.json.scale` as a spacing-like value, while TIFXYZ consumers interpret it as grid cells per voxel

This computes scale from the final emitted grid as `1 / measured_spacing`, keeps `--tifxyz-source` unchanged, and corrects the TIFXYZ format documentation

Added regression coverage for anisotropic spacing, downsampling, normalized UVs, `mesh_units` independence, and source-scale preservation
