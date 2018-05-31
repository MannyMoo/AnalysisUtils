'''Python wrapper for a RooWorkspace. The workspace should be used to create 
all RooVars and RooPDFs to avoid any memory leak/ownership issues.'''

from CharmBaryonLifetimes.data import datadir
import os, ROOT, re
from ROOT import TFile

class Workspace(object) :
    '''Wrapper around a RooWorkspace so it's loaded and saved from a TFile on demand.'''

    __slots__ = ('_file', 'workspace',) + tuple(filter(lambda attr : ' ' not in attr and not attr.startswith('_'),
                                                       dir(ROOT.RooWorkspace)))
    _writedelete = int(ROOT.TObject.kWriteDelete)

    def __init__(self, name, fname = None) :
        self.workspace = None
        self._file = None
        if fname :
            print 'Load workspace from', fname
            self._file = TFile.Open(fname)
            if self._file :
                self.workspace = self._file.Get(name)
                self._file.Close()
            else :
                # Create the file.
                self._file = TFile.Open(fname, 'recreate')
                self._file.Close()
        if not self.workspace :
            self.workspace = ROOT.RooWorkspace(name)
        for attr in self.__slots__[2:] :
            if attr in ('factory',) :
                continue
            setattr(self, attr, getattr(self.workspace, attr))

    def __del__(self) :
        if self._file :
            print 'Save workspace to', self._file.GetName()
            self._file = TFile.Open(self._file.GetName(), 'update')
            self.workspace.Write(self.workspace.GetName(), Workspace._writedelete)
            self._file.Close()

    def roovar(self, name, title = None, val = None, xmin = None, xmax = None, unit = None, error = None, discrete = False) :
        if not discrete :
            if self.workspace.var(name) :
                var = self.workspace.var(name)
            else :
                if xmin != None and xmax != None :
                    var = self.workspace.factory('{0}[{1}, {2}]'\
                                                .format(name, xmin, xmax))
                elif val != None :
                    var = self.workspace.factory('{0}[{1}]'.format(name, val))
                else :
                    raise ValueError('Must give at least xmin & xmax, or val!')
            if None != title : 
                var.SetTitle(title)
            if None != unit :
                var.setUnit(unit)
            if None != val :
                var.setVal(val)
            if None != xmin :
                var.setMin(xmin)
            if None != xmax :
                var.setMax(xmax)
            if None != error :
                var.setError(error)
            return var

        if self.workspace.cat(name) :
            var = self.workspace.cat(name)
        else :
            form = name
            if None != xmin and None != xmax :
                form += '[' + ', '.join(name + str(i) + '=' + str(i) for i in xrange(int(xmin), int(xmax)+1)) + ']'
            else :
                form += '[]'
            var = self.workspace.factory(form)
        if None != val :
            var.setIndex(val)
        if None != title :
            var.SetTitle(title)
        return var
                    
    def factory(self, expr, *args) :
        if args :
            expr += '::' + args[0]
        if len(args) > 1 :
            strargs = []
            for arg in args[1:] :
                if isinstance(arg, ROOT.TObject) :
                    strargs.append(arg.GetName())
                else :
                    strargs.append(str(arg))
            expr += '(' + ', '.join(strargs) + ')'
        return self.workspace.factory(expr)

def findarg(argset, ident) :
    '''Find an object in a RooArgSet or RooArgList. If 'ident' is an int, the object with that index in
    'argset' is returned. If 'ident' is a string, a regex search is performed on the names of each object
    in 'argset' and those that contain the pattern are returned. Otherwise, 'ident' can be a callable which
    is passed each object in 'argset' and should return a bool to determine if it's selected.'''

    iterator = argset.iterator()
    obj = iterator.Next()
    if isinstance(ident, int) :
        i = 0
        while obj and i != ident :
            i += 1
            obj = iterator.Next()
        return obj

    matches = []
    if isinstance(ident, str) :
        check = lambda arg : bool(re.search(ident, arg.GetName()))
    else :
        check = ident
    while obj :
        if check(obj) :
            matches.append(obj)
        obj = iterator.Next()
    return matches

def get_component(pdf, ident) :
    return findarg(pdf.getComponents(), ident)

def get_variable(pdf, ident) :
    return findarg(pdf.getVariables(), ident)

# Giving everything a unique name is a pain, so don't bother persisting
# between sessions.
#workspacefilename = os.path.join(datadir, 'workspace.root')
workspace = Workspace('workspace', 
                      #workspacefilename,
                      )
