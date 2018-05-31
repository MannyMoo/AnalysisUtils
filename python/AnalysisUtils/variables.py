'''Formulae for variables from the TTrees. The variable dicts are in the format
needed by makeroodataset.make_roodataset, for converting TTress to RooDataSets.'''

def var_title(vardict) :
    '''Get the title string including the unit for a variable.'''
    if 'unit' in vardict :
        return vardict['title'] + ' [' + vardict['unit'] + ']'
    return vardict['title']

variables = {'mass' : {'formula' : 'Xc_M',
                       'xmin' : 2300,
                       'xmax' : 2400,
                       'title' : 'Mass', 
                       'unit' : 'MeV', # optional
                       'discrete' : False, #optional, default False.
                       },
             }
