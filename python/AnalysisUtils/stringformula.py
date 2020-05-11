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

    def substitute_variables(self, recursive = True, maxdepth = 1000, **kwargs):
        '''Substitute named variables for other terms.'''
        newform, used = self.get_used_substitutions(recursive = recursive, maxdepth = maxdepth, **kwargs)
        return newform

    def get_used_substitutions(self, recursive = True, maxdepth = 1000, **kwargs):
        '''Substitute named variables for other terms and return the new string and used substitions.'''
        if recursive:
            for fromval, toval in kwargs.items():
                if toval in kwargs and kwargs[toval] == fromval:
                    raise ValueError('Circular substition: {0} -> {1} -> {0}!'.format(fromval, toval))
            prevform = StringFormula(self)
            newform, used = self.get_used_substitutions(False, **kwargs)
            i = 0
            while newform != prevform and i < maxdepth:
                prevform = newform
                newform, _used = newform.get_used_substitutions(False, **kwargs)
                used.update(_used)
                i += 1
            if i == maxdepth:
                raise ValueError(('Exceeded max recursion depth substituting {0!r} using {1!r}\n'\
                                  'Current prevform: {2}\nnewform: {3}').format(self, kwargs, prevform, newform))
            return newform, used

        subform = StringFormula(self)
        prevform = subform
        used = {}
        # Think this should behave as it matches the exact, full variable name.
        for var, sub in kwargs.items():
            # Check if it's a single variable, if not add parentheses
            if not re.match('^[A-Za-z_][A-Za-z0-9_]*$', sub):
                sub = '(' + sub + ')'
            # Is at the start of the string or preceded by a non-variable name character.
            for start, newstart in ('^', ''), ('(?P<newstart>[^A-Za-z0-9_])', '\g<newstart>') :
                # Is at the end of the string or followed by a non-variable name character.
                for end, newend in ('$', ''), ('(?P<newend>[^A-Za-z0-9_])', '\g<newend>'):
                    subform = StringFormula(re.sub(start + var + end, newstart + sub + newend, subform))
            if subform != prevform:
                used[var] = sub
                prevform = subform
        return subform, used

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

    def histo3D(self, variableY, variableZ, name = None, nbins = None, nbinsY = None, nbinsZ = None, suffix = '',
                htype = ROOT.TH3F):
        '''Make a 3D histo.'''
        if None == name:
            name = variableZ.name + '_vs_' + variableY.name + '_vs_' + self.name
        name += suffix
        h = htype(name, '', self._nbins(nbins), self.xmin, self.xmax,
                  variableY._nbins(nbinsY), variableY.xmin, variableY.xmax,
                  variableZ._nbins(nbinsZ), variableZ.xmin, variableZ.xmax)
        self.set_x_title(h)
        variableY.set_y_title(h)
        variableZ.set_z_title(h)
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

    def __init__(self, *args, **kwargs):
        '''Copies arguments into new NamedFormula instances. Adds the option to initialise from a sequence
        of NamedFormula instances.'''
        try:
            super(NamedFormulae, self).__init__({v.name : v for v in args[0]}, **kwargs)
        except (IndexError, AttributeError):
            super(NamedFormulae, self).__init__(*args, **kwargs)
        for name, var in self.items():
            self[name] = NamedFormula(var, name = name)

    def range_selection(self, usealiases = True):
        '''Get the range selection for all formulae.'''
        if not self:
            return StringFormula('true')
        vals = list(self.values())
        sel = vals[0].range_selection(usealiases)
        for val in vals[1:]:
            sel = sel & val.range_selection(usealiases)
        return sel

    def get_var(self, name):
        '''Get the variable of the given name. If name isn't a string (eg, is a NamedFormula or None),
        return name.'''
        if isinstance(name, str):
            return self[name]
        return name

    def histo_string(self, variable, name = None, nbins = None, usealias = True):
        '''Get the string to make a histo with TTree::Draw for the given variable name.'''
        return self.get_var(variable).histo_string(name = name, nbins = nbins, usealias = usealias)

    def histo2D_string(self, variable, variableY, name = None, nbins = None, nbinsY = None, usealias = True):
        '''Get the string to make a 2D histo with TTree::Draw'''
        return self.get_var(variable).histo2D_string(self.get_var(variableY), name = name, nbins = nbins,
                                                     nbinsY = nbinsY, usealias = usealias)

    def histo(self, variable, name = None, nbins = None, suffix = '', htype = ROOT.TH1F):
        '''Make a histo for the given variable with the given range.'''
        return self.get_var(variable).histo(name = name, nbins = nbins, suffix = suffix, htype = htype)

    def histo2D(self, variable, variableY, name = None, nbins = None, nbinsY = None, suffix = '', 
                htype = ROOT.TH2F):
        '''Make a 2D histo with variable on the x-axis and variableY on the y-axis.'''
        return self.get_var(variable).histo2D(self.get_var(variableY), name = name, nbins = nbins, nbinsY = nbinsY,
                                              suffix = suffix, htype = htype)

    def histo3D(self, variable, variableY, variableZ, name = None, nbins = None, nbinsY = None, nbinsZ = None, 
                suffix = '', htype = ROOT.TH3F):
        '''Make a 3D histo.'''
        return self.get_var(variable).histo3D(self.get_var(variableY), self.get_var(variableZ), 
                                              name = name, nbins = nbins, nbinsY = nbinsY, nbinsZ = nbinsZ,
                                              suffix = suffix, htype = htype)
