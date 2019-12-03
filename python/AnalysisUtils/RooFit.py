'''Import RooFit without the annoying banner.'''

from AnalysisUtils.Silence import Silence

try:
    with Silence():
        from ROOT import RooFit
except:
    raise
