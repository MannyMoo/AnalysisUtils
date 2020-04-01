'''Wrapper classes for string formulae.'''

import ROOT

class StringFormula(str):
    '''Combine string variables as if they were numerical types.'''

    def __repr__(self):
        return 'StringFormula("{0}")'.format(self)

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
    _optargs = {'unit' : None, 'discrete' : False, 'nbins' : 100}

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        for val in self._args:
            if not val in self:
                raise NameError('Must include {0!r} in constructor arguments!'.format(val))

    def _name(self, name = None):
        if None != name:
            return name
        return self.name

    def _nbins(self, nbins = None):
        if None != nbins:
            return nbins
        return self.nbins

    def set_alias(self, tree):
        '''Set the alias name -> formula for the given TTree.'''
        tree.SetAlias(self.name, self.formula)
    
    def axis_title(self):
        '''Get the axis title with unit.'''
        if self.unit:
            return '{0} [{1}]'.format(self.title, self.unit)
        return self.title

    def set_axis_title(self, histo, axis = 'x'):
        '''Set the axis title of the histo.'''
        try:
            getattr(histo, 'Get{0}axis'.format(axis.upper()))().SetTitle(self.axis_title())
        except AttributeError:
            pass

    def set_x_title(self, histo):
        '''Set the x-axis title of the histo.'''
        return self.set_axis_title(histo, 'x')

    def set_y_title(self, histo):
        '''Set the y-axis title of the histo.'''
        return self.set_axis_title(histo, 'y')

    def set_z_title(self, histo):
        '''Set the z-axis title of the histo.'''
        return self.set_axis_title(histo, 'z')

    def range_selection(self, usealias = True):
        '''Get the selection requiring the variable to be in range.'''
        if usealias:
            val = StringFormula(self.name)
        else:
            val = StringFormula(self.formula)
        return (self.xmin <= val) & (val <= self.xmax)

    def histo_string(self, name = None, nbins = 100):
        '''Get the string to make a histo with TTree::Draw.'''
        return '{0}({1}, {2}, {3})'.format(self._name(name), nbins, self.xmin, self.xmax)

    def histo(self, name = None, nbins = None, suffix = '', htype = ROOT.TH1F):
        '''Make a histo with the given range.'''
        h = htype(self._name(name) + suffix, '', self._nbins(nbins), self.xmin, self.xmax)
        self.set_x_title(h)
        return h

    def histo2D(self, variableY, name = None, nbins = None, nbinsY = None, suffix = '', htype = ROOT.TH2F):
        '''Make a 2D histo with the given variable on the y-axis.'''
        if None == name:
            name = variableY.name + '_vs_' + self.name
        name += suffix
        h = htype(name, '', self._nbins(nbins), self.xmin, self.xmax,
                  variableY._nbins(nbinsY), variableY.xmin, variableY.xmax)
        self.set_x_title(h)
        variableY.set_y_title(h)
        return h

    def copy(self, **kwargs):
        '''Copy this NamedFormula and update with the given kwargs.'''
        return NamedFormula(self, **kwargs)

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
