
With normalised UVs and the default stretch factor, `vc_obj2tifxyz` rasterized 0 of 4 grid points, wrote a 2×2 tifxyz made only of the `-1` sentinel, printed «Successfully converted» and exited 0. Anything scripting it saw success.

It now refuses to write that directory, prints an error that names the grid size and the two ways out (a stretch factor, or `--uv-to-obj`), and exits 1. The usage line no longer calls the default UV-metric mode «legacy behavior».

Reproduced on main (`be09a8503`) with an OBJ whose UVs are normalised to [0,1], built from the real geometry of a published PHerc0125 segment (`tifxyz_to_obj_normuv.py`, attached):

```
$ vc_obj2tifxyz z6336_w020_normuv.obj out          # before
UV-metric mode: grid 2 x 2  scale(OBJ units): 0.987804, 0.781818
Valid grid points: 0 / 4 (0%)
Warning: no valid grid points were rasterized.
Successfully converted to tifxyz format
exit 0, out/meta.json: bbox [[-1,-1,-1],[-1,-1,-1]]

$ vc_obj2tifxyz z6336_w020_normuv.obj out          # after
Valid grid points: 0 / 4 (0%)
Error: no valid grid points were rasterized on the 2 x 2 grid. If the OBJ's UVs are normalised to [0,1] (published segments), pass a stretch_factor (e.g. 800) or --uv-to-obj=<OBJ units per UV unit>.
Failed to create quad surface
exit 1, nothing written

$ vc_obj2tifxyz z6336_w020_normuv.obj out 800 1.0  # after, with a stretch factor
Valid grid points: 449369 / 496584 (90.492%)
Successfully converted to tifxyz format
exit 0
```

Closes #1320.

The patch was prepared with Claude Code under my direction; I built it and ran the reproduction above locally.

