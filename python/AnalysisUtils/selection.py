'''Selections in TTree format.'''

def AND(*args) :
    return '(' + ') && ('.join(args) + ')'

def OR(*args) :
    return '(' + ') || ('.join(args) + ')'

def NOT(sel) :
    return '!(' + sel + ')'
