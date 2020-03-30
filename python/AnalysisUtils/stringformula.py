class StringFormula(object):
    '''Combine string variables as if they were numerical types.'''

    def __init__(self, formula):
        self.formula = str(formula)

    def __str__(self):
        return self.formula
        
    def __repr__(self):
        return 'StringFormula({0!r})'.format(self.formula)

    def _operator(self, operator, other):
        return StringFormula('({0}) {1} ({2})'.format(self, operator, other))

    def _roperator(self, operator, other):
        return StringFormula('({0}) {1} ({2})'.format(other, operator, self))

for func, op in (('add', '+'),
                 ('sub', '-'),
                 ('mul', '*'),
                 ('div', '/'),
                 ('or', '||'),
                 ('and', '&&'),
                 ('gt', '>'),
                 ('lt', '<'),
                 ('le', '<='),
                 ('ge', '>=')):
    setattr(StringFormula, '__{0}__'.format(func),
            eval('lambda self, other : self._operator({0!r}, other)'.format(op)))
    setattr(StringFormula, '__r{0}__'.format(func),
            eval('lambda self, other : self._roperator({0!r}, other)'.format(op)))

class NamedFormula(object):
    '''A formula with name, title, range, units, and discrete flag.'''

    def __init__(self, name, title, formula, xmin, xmax, unit = None, discrete = False):
        self.name = name
        self.formula = formula
        self.xmin = xmin
        self.xmax = xmax
        self.title = title
        self.unit = unit
        self.discrete = discrete

    def set_alias(self, tree):
        '''Set the alias name -> formula for the given TTree.'''
        tree.SetAlias(self.name, self.formula)
    
    def axis_title(self):
        '''Get the axis title with unit.'''
        if self.unit:
            return '{0} [{1}]'.format(self.title, self.unit)
        return self.title

    def range_selection(self, usealias = True):
        '''Get the selection requiring the variable to be in range.'''
        if usealias:
            val = StringFormula(self.name)
        else:
            val = StringFormula(self.formula)
        return (self.xmin <= val) & (val <= self.xmax)

    def __getitem__(self, name):
        '''So it can be accessed like a dict, for backwards compatibility.'''
        return getattr(self, name)

    def dict(self):
        '''Get the dict of values.'''
        return self.__dict__

class NamedFormulae(dict):
    '''A collection of NamedFormula instances.'''

    def range_selection(self, usealiases = True):
        '''Get the range selection for all formulae.'''
        if not self:
            return StringFormula('true')
        vals = list(self.values())
        sel = vals[0].range_selection(usealiases)
        for val in vals[1:]:
            sel = sel & val.range_selection(usealiases)
        return sel
