'''Get diracutils from AnalysisUtils.'''

import sys, os
sys.path.insert(0, os.path.expandvars('$ANALYSISUTILSROOT/python/AnalysisUtils'))
from diracutils import *
sys.path.pop(0)
