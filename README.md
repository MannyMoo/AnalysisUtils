# Utilities for performing analyses

The code is organised as an LHCb CMake project, so you can build & run it in an LHCb application. Eg,

```
lb-dev DaVinci/v43r1
cd DaVinciDev_v43r1
git clone ssh://git@gitlab.cern.ch:7999/malexand/AnalysisUtils.git
make
```

Then `./run <whatever>` will execute whatever command in the analysis environment, so you can use any of the python modules.

Currently everything is just python and only depends on ROOT, so if you have ROOT installed you can also just add the full path to `python/AnalysisUtils` to your `PYTHONPATH`, eg, if you don't have access to the full LHCb software environment. This isn't guaranteed always to be the case though.

# Directory structure

## python/AnalysisUtils

Shared python modules for core functionality, eg, accessing ntuples/RooDataSets, building fit models, plotting utils.

## scripts

Scripts containing main code for the analysis. These should be fairly minimal with all the functionality living in `python/AnalysisUtils`.
