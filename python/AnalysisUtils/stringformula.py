'''Wrapper classes for string formulae.'''

import ROOT, re

class StringFormula(str):
    '''Combine string variables as if they were numerical types.'''

    def __repr__(self):
        return 'StringFormula("{0}")'.format(self)

    def _operator(self, operator, other):
        return StringFormula('({0}) {1} ({2})'.format(self, operator, other))

    def _roperator(self, operator, other):
        return StringFormula('({0}) {1} ({2})'.format(other, operator, self))

    def named_variables(self):
        '''Get all named variables used in this formula.'''
        return re.findall('[A-Za-z_][A-Za-z0-9_]*', self)

    def substitute_variables(self, recursive = True, **kwargs):
        '''Substitute named variables for other terms.'''
        if recursive:
            for fromval, toval in kwargs.items():
                if toval in kwargs and kwargs[toval] == fromval:
                    raise ValueError('Circular substition: {0} -> {1} -> {0}!'.format(fromval, toval))
            prevform = StringFormula(self)
            newform = self.substitute_variables(False, **kwargs)
            while newform != prevform:
                prevform = newform
                newform = newform.substitute_variables(False, **kwargs)
            return newform

        subform = StringFormula(self)
        # This isn't entirely reliable, as, eg, one of the earlier subsitutions may contain
        # one of the later substitutions as a sub-string. Use of compiler.parse could be
        # safer, but more complicated.
        for var, sub in sorted(kwargs.items(), key = lambda x : len(x[0]), reverse = True):
            subform = StringFormula(subform.replace(var, '(' + sub + ')'))
        return subform

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

    def histo_string(self, name = None, nbins = None, usealias = True):
        '''Get the string to make a histo with TTree::Draw.'''
        return '{4} >> {0}({1}, {2}, {3})'.format(self._name(name), self._nbins(nbins), self.xmin, self.xmax,
                                                  (self.name if usealias else self.formula))

    def histo2D_string(self, variableY, name = None, nbins = None, nbinsY = None, usealias = True):
        '''Get the string to make a 2D histo with TTree::Draw'''
        if None == name:
            name = '{0}_vs_{1}'.format(variableY.name, self.name)
        return '{8} : {7} >> {0}({1}, {2}, {3}, {4}, {5}, {6})'\
            .format(name, self._nbins(nbins), self.xmin, self.xmax,
                    variableY._nbins(nbinsY), variableY.xmin, variableY.xmax,
                    (self.name if usealias else self.formula),
                    (variableY.name if usealias else variableY.formula))

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

    def histo_string(self, variable, name = None, nbins = None, usealias = True):
        '''Get the string to make a histo with TTree::Draw for the given variable name.'''
        return self[variable].histo_string(name = name, nbins = nbins, usealias = usealias)

    def histo2D_string(self, variable, variableY, name = None, nbins = None, nbinsY = None, usealias = True):
        '''Get the string to make a 2D histo with TTree::Draw'''
        return self[variable].histo2D_string(self[variableY], name = name, nbins = nbins, nbinsY = nbinsY,
                                             usealias = usealias)

    def histo(self, variable, name = None, nbins = None, suffix = '', htype = ROOT.TH1F):
        '''Make a histo for the given variable with the given range.'''
        return self[variable].histo(name = name, nbins = nbins, suffix = suffix, htype = htype)

    def histo2D(self, variable, variableY, name = None, nbins = None, nbinsY = None, suffix = '', 
                htype = ROOT.TH2F):
        '''Make a 2D histo with variable on the x-axis and variableY on the y-axis.'''
        return self[variable].histo2D(self[variableY], name = name, nbins = nbins, nbinsY = nbinsY,
                                      suffix = suffix, htype = htype)
