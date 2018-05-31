'''Formulae for variables from the TTrees. The variable dicts are in the format
needed by makeroodataset.make_roodataset, for converting TTress to RooDataSets.'''

def roovar(variables, workspace, name, 
           title = None, val = None, xmin = None, xmax = None, unit = None, error = None) :
    '''Make a RooRealVar with the given attributes. If a variable of the same name is defined
    in the variables dict then the title, xmin, xmax and unit are taken from there.'''

    if name in variables :
        title = variables[name]['title']
        xmin = variables[name]['xmin']
        xmax = variables[name]['xmax']
        unit = variables[name].get('unit', '')
    return workspace.roovar(**locals())

def var_title(vardict) :
    '''Get the title string including the unit for a variable.'''
    if 'unit' in vardict :
        return vardict['title'] + ' [' + vardict['unit'] + ']'
    return vardict['title']
