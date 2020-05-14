'''Selections in TTree format.'''

def combine(args, operator):
    '''Concatenate arguments with the given operator between them.'''
    return '(' + ') {0} ('.format(operator).join(filter(None, args)) + ')'

def AND(*args) :
    '''Take an AND (&&) of the given arguments.'''
    return combine(args, '&&')

def OR(*args) :
    '''Take an OR (||) of the give arguments'''
    return combine(args, '||')

def product(*args):
    '''Returns the product (*) of arguments.'''
    return combine(args, '*')

def NOT(sel) :
    '''Returns !(sel).'''
    return '!(' + sel + ')'
