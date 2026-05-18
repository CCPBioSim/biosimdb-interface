#!/bin/bash

SCHEMA_PATH="/Users/jas.kalayan/Library/CloudStorage/OneDrive-ScienceandTechnologyFacilitiesCouncil/STFC_job/bin/BioSimDR/biosim-schema/"

# echo "------GROMACS MIN------" > file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine gromacs --logfile tests/test_gromacs/example_files/1AKI_minimised.log >> file.log

# echo "------GROMACS PROD------" > file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine gromacs --logfile tests/test_gromacs/example_files/1AKI_production.log >> file.log

# echo "------AMBER------" >> file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine amber --logfile tests/test_amber/example_files/amber_03_Prod.out >> file.log


# DIR="/Users/jas.kalayan/Library/CloudStorage/OneDrive-ScienceandTechnologyFacilitiesCouncil/STFC_job/others_work/kin_chao/PTH2R_simulation/provenance/inputs_and_outputs/5_gromacs/"

# echo "------1. GMX + MDANALYSIS------" > file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine gromacs --logfile ${DIR}step6.6_equilibration.log --top ${DIR}step6.6_equilibration.tpr --traj ${DIR}step6.6_equilibration.xtc >> file.log


# DIR2="/Users/jas.kalayan/Library/CloudStorage/OneDrive-ScienceandTechnologyFacilitiesCouncil/STFC_job/PROJECTS/dinaMISMO/simulation_steps/"

# echo "------2. GMX + MDANALYSIS------" > file.log

# # python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine gromacs --logfile ${DIR2}4.0a_prodb.log --top ${DIR2}4.0a_prodb.tpr --traj ${DIR2}4.0a_prodb.trr >> file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --top ${DIR2}system.prmtop --traj ${DIR2}4.0a_prodb.trr >> file.log


DIR3="/Users/jas.kalayan/Library/CloudStorage/OneDrive-ScienceandTechnologyFacilitiesCouncil/STFC_job/PROJECTS/waterEntropy_project/waterEntropy_run_example/gromacs_aspirin_example/"

echo "------3. GMX + MDANALYSIS------" > file.log

# extract metadata from files
python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --engine gromacs --logfile ${DIR3}4.0a_prod.log --top ${DIR3}4.0a_prod.tpr --traj ${DIR3}4.0a_prod.trr >> file.log

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --top ${DIR3}4.0a_prod.tpr --traj ${DIR3}4.0a_prod.trr >> file.log

# check we can read in webform schema from interface
python biosimdb_interface/schema/helpers.py ${SCHEMA_PATH}/schema_webformfields.json 


# echo "------4. MDANALYSIS------" >> file.log

# DIR4="/Users/jas.kalayan/Library/CloudStorage/OneDrive-ScienceandTechnologyFacilitiesCouncil/STFC_job/others_work/ioana_papa/STV_sim/"

# python biosim_extractor/schema/populateschema.py ${SCHEMA_PATH}schema_enginemappings.json --top ${DIR4}STV_solvated_box.prmtop --traj ${DIR4}STV_100frames.nc >> file.log