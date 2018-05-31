'''Functions for building fit PDFs. Everything is built via the workspace.'''

import ROOT
from AnalysisUtils.variables import variables
from AnalysisUtils.workspace import workspace, get_variable, get_component

def roovar(name, title = None, val = None, xmin = None, xmax = None, unit = None, error = None) :
    '''Make a RooRealVar with the given attributes. If a variable of the same name is defined
    in the variables module then the title, xmin, xmax and unit are taken from there.'''

    if name in variables :
        title = variables[name]['title']
        xmin = variables[name]['xmin']
        xmax = variables[name]['xmax']
        unit = variables[name].get('unit', '')
    return workspace.roovar(**locals())
