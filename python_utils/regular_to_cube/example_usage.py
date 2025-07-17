#!/usr/bin/env python3

"""
Example/test script for grib2_to_cube.py
This script demonstrates how to use the GRIB2 to FV3 cube sphere interpolation tool.
"""

import os
import sys
import subprocess
import argparse

def run_example():
    """Run an example interpolation."""
    
    # Example paths - modify these for your system
    example_config = {
        'grib2_file': '/path/to/your/aerosol_data.grb2',
        'output_dir': '/path/to/fv3/tiles/',
        'grid_spec': '/path/to/fv3_grid_spec.nc',
        'species_mapping': 'species_mapping.json'
    }
    
    print("GRIB2 to FV3 Cube Sphere Interpolation Example")
    print("=" * 50)
    
    # Check if required files exist
    missing_files = []
    for key, path in example_config.items():
        if key != 'species_mapping' and not os.path.exists(path):
            missing_files.append(f"{key}: {path}")
    
    if missing_files:
        print("ERROR: Missing required files:")
        for f in missing_files:
            print(f"  - {f}")
        print("\nPlease update the paths in this script or provide correct file paths.")
        return 1
    
    # Build command
    cmd = [
        'python3', 'grib2_to_cube.py',
        '-i', example_config['grib2_file'],
        '-o', example_config['output_dir'], 
        '-g', example_config['grid_spec'],
        '--species_mapping', example_config['species_mapping'],
        '--vertical_method', 'log_linear',
        '--horizontal_method', 'bilinear',
        '--debug'
    ]
    
    print("Running command:")
    print(" ".join(cmd))
    print()
    
    # Run the interpolation
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("SUCCESS: Interpolation completed successfully")
        print("\nOutput:")
        print(result.stdout)
        if result.stderr:
            print("\nWarnings/Errors:")
            print(result.stderr)
        return 0
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Interpolation failed with return code {e.returncode}")
        print(f"\nStdout:\n{e.stdout}")
        print(f"\nStderr:\n{e.stderr}")
        return 1
    except FileNotFoundError:
        print("ERROR: Could not find grib2_to_cube.py script")
        print("Make sure you're running this from the correct directory")
        return 1

def check_dependencies():
    """Check if required Python packages are installed."""
    
    required_packages = [
        'xarray',
        'numpy', 
        'grib2io',
        'ESMF',
        'scipy'
    ]
    
    print("Checking dependencies...")
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} (missing)")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    else:
        print("\nAll dependencies satisfied!")
        return True

def print_usage():
    """Print usage information."""
    
    print("""
GRIB2 to FV3 Cube Sphere Interpolation Tool

This tool interpolates aerosol species data from GRIB2 files on regular grids
to FV3 cube sphere grids and writes to existing netCDF files.

USAGE:
    python grib2_to_cube.py -i INPUT.grb2 -o OUTPUT_DIR -g GRID_SPEC.nc

EXAMPLE:
    python grib2_to_cube.py \\
        -i aerosol_20230101.grb2 \\
        -o /data/fv3/tiles/ \\
        -g /reference/C384_grid_spec.nc \\
        --species_mapping species_mapping.json \\
        --vertical_method log_linear

REQUIRED FILES:
    1. Input GRIB2 file with aerosol species on pressure levels
    2. Output directory with existing FV3 tile files:
       - fv_tracer.res.tile1.nc
       - fv_tracer.res.tile2.nc  
       - fv_tracer.res.tile3.nc
       - fv_tracer.res.tile4.nc
       - fv_tracer.res.tile5.nc
       - fv_tracer.res.tile6.nc
    3. FV3 grid specification file with cube sphere coordinates

OPTIONAL FILES:
    - species_mapping.json: Maps GRIB2 parameter names to FV3 variable names

For more information, see README.md
""")

def main():
    """Main function."""
    
    parser = argparse.ArgumentParser(description='Example/test script for GRIB2 to FV3 interpolation')
    parser.add_argument('--check-deps', action='store_true', 
                       help='Check if required dependencies are installed')
    parser.add_argument('--usage', action='store_true',
                       help='Show usage information') 
    parser.add_argument('--run-example', action='store_true',
                       help='Run example interpolation (modify paths in script first)')
    
    args = parser.parse_args()
    
    if args.check_deps:
        deps_ok = check_dependencies()
        return 0 if deps_ok else 1
    elif args.usage:
        print_usage()
        return 0
    elif args.run_example:
        return run_example()
    else:
        print("GRIB2 to FV3 Cube Sphere Interpolation - Example Script")
        print("\nOptions:")
        print("  --check-deps    Check if required Python packages are installed")
        print("  --usage         Show detailed usage information")
        print("  --run-example   Run example interpolation (modify paths first)")
        print("\nFor the main interpolation tool, use: python grib2_to_cube.py --help")
        return 0

if __name__ == "__main__":
    sys.exit(main())
