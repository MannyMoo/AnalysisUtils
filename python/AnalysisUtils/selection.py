'''Selections in TTree format.'''

def AND(*args) :
    return '(' + ') && ('.join(filter(None, args)) + ')'

def OR(*args) :
    return '(' + ') || ('.join(filter(None, args)) + ')'

def NOT(sel) :
    return '!(' + sel + ')'
