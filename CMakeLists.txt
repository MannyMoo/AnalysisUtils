################################################################################
# Package: AnalysisUtils
################################################################################
gaudi_subdir(AnalysisUtils v0r1)

gaudi_depends_on_subdirs(GaudiConfUtils)

find_package(PythonLibs)
find_package(Boost COMPONENTS program_options REQUIRED)
find_package(ROOT COMPONENTS Core RIO Hist Graf Graf3d Postscript Gpad
                             RooFit RooFitCore Tree MathCore Foam Physics
                             Proof ProofBench ProofDraw ProofPlayer
			     ROOTDataFrame)

# Runtime dependency of libROOTDataFrame.so
find_library(Davix_LIB NAMES davix)
if(Davix_LIB)
  get_filename_component(Davix_LIB_DIR "${Davix_LIB}" DIRECTORY)
  gaudi_env(PREPEND LD_LIBRARY_PATH "${Davix_LIB_DIR}")
endif()

# override the genreflex call to wrap it in the right environment
# set(ROOT_genreflex_CMD ${env_cmd} --xml ${env_xml} ${ROOT_genreflex_CMD})

include_directories(SYSTEM ${Boost_INCLUDE_DIRS} ${ROOT_INCLUDE_DIRS})
# gaudi_add_dictionary(AnalysisUtils
#                      dict/AnalysisUtilsDict.h dict/AnalysisUtilsDict.xml
#                      SPLIT_CLASSDEF)

# gaudi_add_library(AnalysisUtilsLib
#                   src/*.cpp
#                   AnalysisUtilsDict_classdef.cpp
#                   PUBLIC_HEADERS AnalysisUtils
#                   INCLUDE_DIRS Boost ROOT
#                   LINK_LIBRARIES Boost ROOT)

gaudi_add_module(AnalysisUtils
                 src/*.cpp
                 LINK_LIBRARIES LinkerEvent MCEvent PhysEvent TrackEvent RelationsLib DaVinciKernelLib DaVinciMCKernelLib
		 INCLUDE_DIRS Boost ROOT)

# # ensure that genreflex is not called twice (in parallel builds)
# add_dependencies(AnalysisUtilsLib AnalysisUtilsGen)

gaudi_install_python_modules()

#gaudi_add_test(QMTest QMTEST)
