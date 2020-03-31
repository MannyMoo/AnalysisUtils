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

class NamedFormula(dict):
    '''A formula with name, title, range, units, and discrete flag.'''

    _args = 'name', 'title', 'formula', 'xmin', 'xmax'
    _optargs = {'unit' : None, 'discrete' : False}

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        for val in self._args:
            if not val in self:
                raise NameError('Must include {0!r} in constructor arguments!'.format(val))

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

    def histo_string(self, name = None, nbins = 100):
        if not name:
            name = self.name
        return '{0}({1}, {2}, {3})'.format(name, nbins, self.xmin, self.xmax)

for arg in NamedFormula._args:
    setattr(NamedFormula, arg, property(fget = eval('lambda self : self[{0!r}]'.format(arg)),
                                        fset = eval('lambda self, val : self.__setitem__({0!r}, val)'.format(arg))))
for arg, default in NamedFormula._optargs.items():
    setattr(NamedFormula, arg, property(fget = eval('lambda self : self.get({0!r}, {1!r})'.format(arg, default)),
                                        fset = eval('lambda self, val : self.__setitem__({0!r}, val)'.format(arg))))

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
