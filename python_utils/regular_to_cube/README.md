# GRIB2 to FV3 Cube Sphere Interpolation

This script reads GRIB2 files containing aerosol species on model levels on a regular grid and interpolates them horizontally and vertically to an FV3 cube sphere grid, writing the results to existing netCDF files.

## Features

- Reads GRIB2 files with multiple aerosol species and pressure levels
- Horizontal interpolation using ESMF (Earth System Modeling Framework)
- Vertical interpolation with multiple methods (linear, log-linear, nearest)
- Supports all 6 FV3 cube sphere tiles
- Configurable species mapping between GRIB2 and FV3 naming conventions

## Requirements

```bash
pip install xarray numpy grib2io ESMF scipy
```

Note: ESMF may require additional system dependencies. On HPC systems, it's often available as a module:
```bash
module load esmf
```

## Usage

### Basic Usage

```bash
python grib2_to_cube.py \
    -i input_aerosol_file.grb2 \
    -o /path/to/fv3/output/tiles/ \
    -g /path/to/fv3_grid_spec.nc
```

### Advanced Usage

```bash
python grib2_to_cube.py \
    -i input_aerosol_file.grb2 \
    -o /path/to/fv3/output/tiles/ \
    -g /path/to/fv3_grid_spec.nc \
    --species_mapping species_mapping.json \
    --vertical_method log_linear \
    --horizontal_method bilinear \
    --time_index 0 \
    --debug
```

## Arguments

- `-i, --input`: Input GRIB2 file path (required)
- `-o, --output_dir`: Directory containing FV3 tile files (required)
- `-g, --grid_spec`: FV3 grid specification file for coordinates (required)
- `-t, --time_index`: Time index to update in output files (default: 0)
- `--species_mapping`: JSON file mapping GRIB2 parameters to FV3 variable names
- `--vertical_method`: Vertical interpolation method (linear, log_linear, nearest)
- `--horizontal_method`: Horizontal interpolation method (bilinear, patch, nearest_stod, nearest_dtos)
- `--debug`: Enable debug logging

## Input Files

### GRIB2 File Structure
The input GRIB2 file should contain:
- Aerosol species data on multiple pressure levels
- Regular lat/lon grid
- Standard GRIB2 parameter encoding for aerosols (discipline=0, parameterCategory=20)

The script uses `grib2io` for reading GRIB2 files, which provides efficient access to GRIB2 data and metadata.

### FV3 Output Files
The script expects existing FV3 tile files named:
- `fv_tracer.res.tile1.nc`
- `fv_tracer.res.tile2.nc` 
- `fv_tracer.res.tile3.nc`
- `fv_tracer.res.tile4.nc`
- `fv_tracer.res.tile5.nc`
- `fv_tracer.res.tile6.nc`

Each file should have the standard FV3 structure with:
- Dimensions: `Time`, `zaxis_1` (vertical), `yaxis_1`, `xaxis_1`
- Aerosol species variables (so4, bc1, bc2, oc1, oc2, dust1-5, seas1-4)

### Grid Specification File
The grid specification file should contain FV3 cube sphere grid coordinates:
- `grid_lont`: Longitude coordinates for tile centers
- `grid_latt`: Latitude coordinates for tile centers

## Species Mapping

The script uses a configurable mapping between GRIB2 parameter names and FV3 variable names. Create a JSON file like:

```json
{
  "SO4": "so4",
  "BC1": "bc1",
  "BC2": "bc2",
  "OC1": "oc1",
  "OC2": "oc2",
  "DUST1": "dust1",
  "DUST2": "dust2",
  "DUST3": "dust3",
  "DUST4": "dust4", 
  "DUST5": "dust5",
  "SEAS1": "seas1",
  "SEAS2": "seas2",
  "SEAS3": "seas3",
  "SEAS4": "seas4"
}
```

## Interpolation Methods

### Vertical Interpolation
- **linear**: Linear interpolation in pressure coordinates
- **log_linear**: Linear interpolation in log(concentration) space (recommended for aerosols)
- **nearest**: Nearest neighbor interpolation

### Horizontal Interpolation (ESMF)
- **bilinear**: Bilinear interpolation (default, good balance of speed and accuracy)
- **patch**: Higher-order patch recovery (more accurate but slower)
- **nearest_stod**: Nearest neighbor (source to destination)
- **nearest_dtos**: Nearest neighbor (destination to source)

## Output

The script updates the existing FV3 tile files in place, modifying the aerosol species variables at the specified time index. The original file structure and other variables are preserved.

## Error Handling

- Missing species in GRIB2 data: Warning logged, variable skipped
- Missing variables in FV3 files: Warning logged, variable skipped  
- Grid dimension mismatches: Error logged, processing halted
- File I/O errors: Error logged with details

## Example Workflow

1. Prepare your GRIB2 file with aerosol species data
2. Ensure FV3 tile files exist in the output directory
3. Create/modify species mapping file if needed
4. Run the script:

```bash
python grib2_to_cube.py \
    -i aerosol_data_20230101.grb2 \
    -o /scratch/fv3_output/20230101/ \
    -g /reference/fv3_grid_spec_C384.nc \
    --species_mapping my_species_mapping.json \
    --vertical_method log_linear
```

5. Check the log output for any warnings or errors
6. Verify the updated FV3 files contain the interpolated data

## Troubleshooting

### Common Issues

1. **ESMF import errors**: Ensure ESMF is properly installed and the environment is set up
2. **Missing GRIB2 parameters**: Check the parameter names in your GRIB2 file and update the species mapping
3. **Grid coordinate issues**: Verify the grid specification file has the correct coordinate variables
4. **Memory issues**: For high-resolution grids, consider processing tiles sequentially or reducing data precision

### Debug Mode

Use `--debug` flag to get detailed logging information about:
- GRIB2 file contents and structure
- Grid dimensions and coordinate ranges
- Interpolation progress and statistics
- File I/O operations
