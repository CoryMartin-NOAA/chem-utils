#!/usr/bin/env python3

"""
Script to read GRIB2 files containing aerosol species on model levels 
and interpolate horizontally and vertically to FV3 cube sphere grid.
The script writes to existing netCDF files on the cube sphere grid.

Author: Created for AQM-Utils project
Date: July 2025
"""

import xarray as xr
import numpy as np
import grib2io
import ESMF
import argparse
import sys
import os
from datetime import datetime
from scipy.interpolate import interp1d
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Interpolate GRIB2 aerosol data to FV3 cube sphere grid'
    )
    
    parser.add_argument('-i', '--input', 
                        help='Input GRIB2 file path',
                        required=True)
    
    parser.add_argument('-o', '--output_dir',
                        help='Output directory containing FV3 tile files',
                        required=True)
    
    parser.add_argument('-g', '--grid_spec',
                        help='FV3 grid specification file (for coordinates)',
                        required=True)
    
    parser.add_argument('-t', '--time_index',
                        help='Time index to update in output files (default: 0)',
                        type=int, default=0)
    
    parser.add_argument('--species_mapping',
                        help='JSON file mapping GRIB2 parameters to FV3 variable names',
                        default=None)
    
    parser.add_argument('--vertical_method',
                        help='Vertical interpolation method (linear, log_linear, nearest)',
                        choices=['linear', 'log_linear', 'nearest'],
                        default='linear')
    
    parser.add_argument('--horizontal_method',
                        help='Horizontal interpolation method for ESMF',
                        choices=['bilinear', 'patch', 'nearest_stod', 'nearest_dtos'],
                        default='bilinear')
    
    parser.add_argument('--debug',
                        help='Enable debug logging',
                        action='store_true')
    
    return parser.parse_args()

def setup_logging(debug=False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(level)

def get_default_species_mapping():
    """Default mapping from GRIB2 parameters to FV3 variable names."""
    return {
        # Example mappings - adjust based on your GRIB2 file structure
        'SO4': 'so4',        # Sulfate
        'BC1': 'bc1',        # Hydrophobic black carbon
        'BC2': 'bc2',        # Hydrophilic black carbon  
        'OC1': 'oc1',        # Hydrophobic organic carbon
        'OC2': 'oc2',        # Hydrophilic organic carbon
        'DUST1': 'dust1',    # Dust bin 1
        'DUST2': 'dust2',    # Dust bin 2
        'DUST3': 'dust3',    # Dust bin 3
        'DUST4': 'dust4',    # Dust bin 4
        'DUST5': 'dust5',    # Dust bin 5
        'SEAS1': 'seas1',    # Sea salt bin 1
        'SEAS2': 'seas2',    # Sea salt bin 2
        'SEAS3': 'seas3',    # Sea salt bin 3
        'SEAS4': 'seas4',    # Sea salt bin 4
    }

def load_species_mapping(mapping_file):
    """Load species mapping from JSON file."""
    if mapping_file and os.path.exists(mapping_file):
        import json
        with open(mapping_file, 'r') as f:
            return json.load(f)
    else:
        return get_default_species_mapping()

def read_grib2_data(grib_file):
    """
    Read GRIB2 file and extract aerosol species data using grib2io.
    
    Returns:
        dict: Dictionary containing lat, lon, pressure levels, and species data
    """
    logger.info(f"Reading GRIB2 file: {grib_file}")
    
    # Open GRIB2 file
    grb = grib2io.open(grib_file)
    
    # Initialize data structure
    data = {
        'lats': None,
        'lons': None,
        'pressure_levels': [],
        'species': {}
    }
    
    # Read through all messages to collect data
    for msg in grb:
        try:
            # Get basic grid information
            if data['lats'] is None:
                data['lats'], data['lons'] = msg.latlons()
                logger.info(f"Grid shape: {data['lats'].shape}")
            
            # Get pressure level information
            if hasattr(msg, 'level'):
                level = msg.level
            elif hasattr(msg, 'typeOfLevel') and hasattr(msg, 'scaledValueOfFirstFixedSurface'):
                # For pressure levels, grib2io typically uses scaledValueOfFirstFixedSurface
                if msg.typeOfLevel == 'isobaricInhPa':
                    level = msg.scaledValueOfFirstFixedSurface
                else:
                    level = msg.scaledValueOfFirstFixedSurface if hasattr(msg, 'scaledValueOfFirstFixedSurface') else 0
            else:
                level = 0  # Surface level
            
            # Get parameter information
            param_name = msg.shortName if hasattr(msg, 'shortName') else f"param_{msg.parameterNumber}"
            
            # For aerosol parameters, we might need to use discipline/category/number
            if hasattr(msg, 'discipline') and hasattr(msg, 'parameterCategory') and hasattr(msg, 'parameterNumber'):
                if msg.discipline == 0 and msg.parameterCategory == 20:  # Atmospheric chemistry
                    # Map parameter numbers to common names
                    aerosol_params = {
                        1: 'SO4',    # Sulfate
                        2: 'BC1',    # Black carbon (hydrophobic)
                        3: 'BC2',    # Black carbon (hydrophilic)
                        4: 'OC1',    # Organic carbon (hydrophobic)
                        5: 'OC2',    # Organic carbon (hydrophilic)
                        6: 'DUST1',  # Dust bin 1
                        7: 'DUST2',  # Dust bin 2
                        8: 'DUST3',  # Dust bin 3
                        9: 'DUST4',  # Dust bin 4
                        10: 'DUST5', # Dust bin 5
                        11: 'SEAS1', # Sea salt bin 1
                        12: 'SEAS2', # Sea salt bin 2
                        13: 'SEAS3', # Sea salt bin 3
                        14: 'SEAS4', # Sea salt bin 4
                    }
                    if msg.parameterNumber in aerosol_params:
                        param_name = aerosol_params[msg.parameterNumber]
            
            # Extract data values
            values = msg.data()
            
            # Store data organized by species and level
            if param_name not in data['species']:
                data['species'][param_name] = {}
            
            data['species'][param_name][level] = values
            
            if level not in data['pressure_levels']:
                data['pressure_levels'].append(level)
                
            logger.debug(f"Read {param_name} at level {level}, shape: {values.shape}")
            
        except Exception as e:
            logger.warning(f"Error reading GRIB message: {e}")
            continue
    
    grb.close()
    
    # Sort pressure levels
    data['pressure_levels'] = sorted(data['pressure_levels'])
    logger.info(f"Found {len(data['pressure_levels'])} pressure levels")
    logger.info(f"Found {len(data['species'])} species: {list(data['species'].keys())}")
    
    return data

def create_source_grid(lats, lons):
    """Create ESMF source grid from regular lat/lon data."""
    logger.debug("Creating source grid")
    
    # Ensure we have 2D arrays
    if lats.ndim == 1:
        lons_2d, lats_2d = np.meshgrid(lons, lats)
    else:
        lats_2d, lons_2d = lats, lons
    
    # Create ESMF grid
    grid = ESMF.Grid(np.array(lats_2d.shape), 
                     staggerloc=ESMF.StaggerLoc.CENTER,
                     coord_sys=ESMF.CoordSys.SPH_DEG)
    
    # Add coordinates
    grid_lat = grid.get_coords(1)
    grid_lon = grid.get_coords(0)
    
    grid_lat[...] = lats_2d
    grid_lon[...] = lons_2d
    
    return grid

def create_target_grid_from_file(grid_file, tile_num):
    """Create ESMF target grid from FV3 grid specification file."""
    logger.debug(f"Creating target grid for tile {tile_num}")
    
    # Read grid specification file
    ds_grid = xr.open_dataset(grid_file)
    
    # Extract coordinates for the specific tile
    # Grid files typically have variables like 'grid_lont', 'grid_latt'
    if f'tile{tile_num}' in ds_grid.dims:
        # Multi-tile file
        tile_dim = f'tile{tile_num}'
        lons = ds_grid[f'grid_lont'].sel({tile_dim: 0})
        lats = ds_grid[f'grid_latt'].sel({tile_dim: 0})
    else:
        # Single tile file or need to determine naming convention
        lons = ds_grid['grid_lont']
        lats = ds_grid['grid_latt']
    
    # Create ESMF grid
    grid = ESMF.Grid(np.array(lats.shape),
                     staggerloc=ESMF.StaggerLoc.CENTER,
                     coord_sys=ESMF.CoordSys.SPH_DEG)
    
    # Add coordinates
    grid_lat = grid.get_coords(1)
    grid_lon = grid.get_coords(0)
    
    grid_lat[...] = lats.values
    grid_lon[...] = lons.values
    
    ds_grid.close()
    
    return grid

def create_regridder(src_grid, dst_grid, method='bilinear'):
    """Create ESMF regridding object."""
    logger.debug(f"Creating regridder with method: {method}")
    
    # Map method names to ESMF constants
    method_map = {
        'bilinear': ESMF.RegridMethod.BILINEAR,
        'patch': ESMF.RegridMethod.PATCH,
        'nearest_stod': ESMF.RegridMethod.NEAREST_STOD,
        'nearest_dtos': ESMF.RegridMethod.NEAREST_DTOS
    }
    
    regrid = ESMF.Regrid(src_grid, dst_grid,
                        regrid_method=method_map[method],
                        unmapped_action=ESMF.UnmappedAction.IGNORE)
    
    return regrid

def interpolate_vertical(data_3d, src_levels, dst_levels, method='linear'):
    """
    Interpolate data vertically from source to destination pressure levels.
    
    Args:
        data_3d: 3D array (level, lat, lon) 
        src_levels: Source pressure levels
        dst_levels: Destination pressure levels
        method: Interpolation method
    
    Returns:
        3D array interpolated to destination levels
    """
    logger.debug(f"Vertical interpolation: {len(src_levels)} -> {len(dst_levels)} levels")
    
    # Ensure levels are in ascending order for interpolation
    if src_levels[0] > src_levels[-1]:
        src_levels = src_levels[::-1]
        data_3d = data_3d[::-1, :, :]
    
    if dst_levels[0] > dst_levels[-1]:
        dst_levels = dst_levels[::-1]
        reverse_output = True
    else:
        reverse_output = False
    
    # Prepare output array
    output_shape = (len(dst_levels),) + data_3d.shape[1:]
    interpolated = np.zeros(output_shape)
    
    # Interpolate at each horizontal grid point
    for i in range(data_3d.shape[1]):
        for j in range(data_3d.shape[2]):
            profile = data_3d[:, i, j]
            
            # Skip if all values are masked/invalid
            if np.all(np.isnan(profile)) or np.all(profile == 0):
                interpolated[:, i, j] = 0
                continue
            
            # Create interpolation function
            if method == 'log_linear':
                # Log-linear interpolation (useful for atmospheric data)
                valid_mask = (profile > 0) & np.isfinite(profile)
                if np.sum(valid_mask) < 2:
                    interpolated[:, i, j] = 0
                    continue
                f = interp1d(src_levels[valid_mask], np.log(profile[valid_mask]), 
                           kind='linear', bounds_error=False, fill_value=0)
                interpolated[:, i, j] = np.exp(f(dst_levels))
            else:
                # Linear or nearest interpolation
                f = interp1d(src_levels, profile, kind=method,
                           bounds_error=False, fill_value=0)
                interpolated[:, i, j] = f(dst_levels)
    
    # Reverse output if needed
    if reverse_output:
        interpolated = interpolated[::-1, :, :]
    
    return interpolated

def process_tile(tile_num, grib_data, grid_file, output_dir, species_mapping, 
                 time_index, vertical_method, horizontal_method):
    """Process a single FV3 tile."""
    logger.info(f"Processing tile {tile_num}")
    
    # Create source and target grids
    src_grid = create_source_grid(grib_data['lats'], grib_data['lons'])
    dst_grid = create_target_grid_from_file(grid_file, tile_num)
    
    # Create regridder
    regridder = create_regridder(src_grid, dst_grid, horizontal_method)
    
    # Load existing tile file
    tile_file = os.path.join(output_dir, f'fv_tracer.res.tile{tile_num}.nc')
    if not os.path.exists(tile_file):
        logger.error(f"Output file not found: {tile_file}")
        return False
    
    logger.info(f"Updating file: {tile_file}")
    ds_tile = xr.open_dataset(tile_file, mode='r+')
    
    # Get target pressure levels from the file
    if 'zaxis_1' in ds_tile.coords:
        dst_pressure_levels = ds_tile['zaxis_1'].values
    else:
        logger.error("Cannot find vertical coordinate in output file")
        return False
    
    # Process each species
    for grib_param, fv3_var in species_mapping.items():
        if grib_param not in grib_data['species']:
            logger.warning(f"Species {grib_param} not found in GRIB data")
            continue
            
        if fv3_var not in ds_tile.variables:
            logger.warning(f"Variable {fv3_var} not found in output file")
            continue
        
        logger.info(f"Processing {grib_param} -> {fv3_var}")
        
        # Organize 3D data (level, lat, lon)
        species_data = grib_data['species'][grib_param]
        levels = sorted(species_data.keys())
        
        # Stack data into 3D array
        data_3d = np.stack([species_data[level] for level in levels], axis=0)
        
        # Vertical interpolation
        data_interp_vert = interpolate_vertical(data_3d, levels, dst_pressure_levels, vertical_method)
        
        # Horizontal interpolation for each level
        data_final = np.zeros((len(dst_pressure_levels), dst_grid.size[1], dst_grid.size[0]))
        
        for k in range(len(dst_pressure_levels)):
            # Create ESMF fields
            src_field = ESMF.Field(src_grid, staggerloc=ESMF.StaggerLoc.CENTER)
            dst_field = ESMF.Field(dst_grid, staggerloc=ESMF.StaggerLoc.CENTER)
            
            # Copy data to source field
            src_field.data[...] = data_interp_vert[k, :, :]
            
            # Regrid
            dst_field = regridder(src_field, dst_field)
            
            # Copy to output array
            data_final[k, :, :] = dst_field.data
        
        # Update the netCDF file
        # Ensure proper dimension ordering (Time, zaxis_1, yaxis_1, xaxis_1)
        data_final_4d = data_final[np.newaxis, :, :, :]  # Add time dimension
        
        try:
            ds_tile[fv3_var][time_index, :, :, :] = data_final_4d[0, :, :, :]
            logger.info(f"Successfully updated {fv3_var}")
        except Exception as e:
            logger.error(f"Error updating {fv3_var}: {e}")
    
    # Close the file to save changes
    ds_tile.close()
    
    # Clean up ESMF objects
    regridder.destroy()
    src_grid.destroy()
    dst_grid.destroy()
    
    logger.info(f"Completed tile {tile_num}")
    return True

def main():
    """Main function."""
    args = parse_args()
    setup_logging(args.debug)
    
    logger.info("Starting GRIB2 to FV3 cube sphere interpolation")
    
    # Load species mapping
    species_mapping = load_species_mapping(args.species_mapping)
    logger.info(f"Using species mapping: {species_mapping}")
    
    # Read GRIB2 data
    try:
        grib_data = read_grib2_data(args.input)
    except Exception as e:
        logger.error(f"Failed to read GRIB2 file: {e}")
        return 1
    
    # Process each tile (FV3 cube sphere has 6 tiles)
    success_count = 0
    for tile_num in range(1, 7):
        try:
            success = process_tile(tile_num, grib_data, args.grid_spec, 
                                 args.output_dir, species_mapping,
                                 args.time_index, args.vertical_method, 
                                 args.horizontal_method)
            if success:
                success_count += 1
        except Exception as e:
            logger.error(f"Failed to process tile {tile_num}: {e}")
    
    logger.info(f"Successfully processed {success_count}/6 tiles")
    
    if success_count == 6:
        logger.info("All tiles processed successfully")
        return 0
    else:
        logger.error("Some tiles failed to process")
        return 1

if __name__ == "__main__":
    sys.exit(main())
