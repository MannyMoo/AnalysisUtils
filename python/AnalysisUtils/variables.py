'''Formulae for variables from the TTrees. The variable dicts are in the format
needed by makeroodataset.make_roodataset, for converting TTress to RooDataSets.'''

def var_title(vardict) :
    '''Get the title string including the unit for a variable.'''
    if 'unit' in vardict :
        return vardict['title'] + ' [' + vardict['unit'] + ']'
    return vardict['title']