#!/bin/env python

'''Functionality needed to make a RooDataSet from a TTree.'''

import ROOT
from AnalysisUtils.treeutils import TreeFormula, make_chain

class TreeVar(object) :
    '''Proxy class between a variable, or function of variables, in a TTree and a RooRealVar.'''

    def __init__(self, tree, name, title, formula, xmin, xmax, unit = '', discrete = False) :
        '''tree: the TTree from which to extract the value of the RooRealVar.
        name: name of the RooRealVar.
        formula: either a string representing a variable or function of variables from 
        the TTree, or a python function that can be called with the TTree as argument and return
        a float.
        xmin & xmax: the range of the RooRealVar.'''

        self.xmin = xmin
        self.xmax = xmax
        if not discrete :
            self.var = ROOT.RooRealVar(name, title, xmin + (xmax-xmin)/2., xmin, xmax, unit)
            self._set = self.var.setVal
            self._get = self.var.getVal
            self._str = lambda : 'Name: {0}, Title: {1}, Formula: {2!r}, Value: {3}, Min: {4}, Max: {5}, Unit: {6}, Discrete: False'\
                .format(self.var.GetName(), self.var.GetTitle(), self.formula, self.value, self.var.getMin(), 
                        self.var.getMax(), self.var.getUnit())
        else :
            self.var = ROOT.RooCategory(name, title)
            self._set = lambda v : self.var.setIndex(int(v))
            self._get = self.var.getIndex
            self._str = lambda : 'Name: {0}, Title: {1}, Formula: {2!r}, Value: {3}, Discrete: True'\
                .format(self.var.GetName(), self.var.GetTitle(), self.formula, self.value)
            for i in xrange(int(xmin), int(xmax)+1) :
                self.var.defineType(name + str(i), i)
        self.tree = tree
        self.formula = formula
        if isinstance(formula, str) :
            self.form = TreeFormula(name, formula, tree)
        else :
            self.form = formula
        self.value = self._get()

    def set_var(self) :
        '''Set the value of the RooRealVar from the TTree.'''
        self.value = self.form(self.tree)
        self._set(self.value)
        return self.var

    def is_in_range(self) :
        '''Check if the current value of the variable is in the allowed range.'''
        return self.xmin <= self.value and self.value <= self.xmax

    def __str__(self) :
        return self._str()
                                                                      
def make_roodataset(dataname, datatitle, tree, nentries = -1, selection = '', 
                    ignorecompilefails = False, weightvarname = None, **variables) :
    '''dataname: name of the RooDataSet to be made.
    datatitle: title of the RooDataSet.
    tree: TTree to take the data from.
    nentries: number of entries to use.
    selection: selection formula to apply.
    variables: the keyword should be the name of the RooRealVar to be made. The argument
    value should be a dict containing the keys 'title', 'formula', 'xmin', 'xmax', and optionally
    'unit'. eg:
    
    make_roodataset('massdata', 'massdata', tree, 
                    mass = {'title' : 'B mass','formula' : 'lab0_M', 'xmin' : 5200, 'xmax', 5800, 'unit' : 'MeV'})'''

    print 'Constructing RooDataSet from TTree', tree.GetName()
    rooargs = ROOT.RooArgSet()
    treevars = []
    print 'Variables:'
    skippedvars = []
    for var, args in variables.items() :
        treevar = TreeVar(tree, var, **args)
        if not treevar.form.is_ok() :
            if ignorecompilefails :
                skippedvars.append(treevar)
                continue
            raise ValueError('Variable doesn\'t compile:\n' + str(treevar))
        print treevar
        treevars.append(treevar)
        rooargs.add(treevar.var)
    if skippedvars :
        print 'Variables that don\'t compile and were skipped:'
        for treevar in skippedvars :
            print treevar

    if selection :
        print 'Applying selection', repr(selection)
        selvar = TreeFormula('selection', selection, tree)
        
    else :
        selvar = lambda : True

    if weightvarname :
        print 'Using variable', weightvarname, 'as weight'
        dataset = ROOT.RooDataSet(dataname, datatitle, rooargs, weightvarname)
        weight = lambda : rooargs[weightvarname].getVal()
    else :
        dataset = ROOT.RooDataSet(dataname, datatitle, rooargs)
        weight = lambda : 1.

    if -1 == nentries :
        nentries = tree.GetEntries()
    else :
        nentries = min(tree.GetEntries(), nentries)

    nfailsel = 0
    noutofrange = 0

    for i in xrange(nentries) :
        tree.LoadTree(i)
        if not selvar() :
            nfailsel += 1
            continue
        inrange = True
        for var in treevars :
            var.set_var()
            if not var.is_in_range() :
                inrange = False
                noutofrange += 1
                break
        if inrange :
            dataset.add(rooargs, weight())

    print 'Read', nentries, 'entries from TTree', tree.GetName() + '.'
    print 'Selected', dataset.numEntries(), 'entries.'
    if selection :
        print 'Rejected', nfailsel, 'entries using selection', repr(selection) + '.'
    print 'Rejected', noutofrange, 'entries for being out of range.'

    return dataset

def make_roodatahist(name, roodata, variable, selection = None, nbins = 100, xmin = None, xmax = None) :
    '''Make a 1D binned RooDataHist from an unbinned RooDataSet for the give variable.
    'selection' can be a dictionary with variable names as keys and (min, max) as values,
    or a function that expects a RooArgSet and returns a bool.'''

    if not selection :
        selection = lambda args : True
    elif isinstance(selection, dict) :
        _selection = selection
        selection = lambda args : all(cut[0] <= args[var].getVal() < cut[1] for var, cut in _selection.items())
    
    if None == xmin :
        xmin = variable.getMin()
    if None == xmax :
        xmax = variable.getMax()

    varname = variable.GetName()
    h = ROOT.TH1F(name + '_histo', '', nbins, xmin, xmax)
    for i in xrange(roodata.numEntries()) :
        args = roodata.get(i)
        if not selection(args) :
            continue
        h.Fill(args[varname].getVal(), roodata.weight())
    return ROOT.RooDataHist(name, name, ROOT.RooArgList(variable), h)

def main() :
    '''Read the input file, etc, from the commandline and build the RooDataSet. 
    Variables to be read into the RooDataSet are passed as additional commandline
    arguments. Arguments should be the title, formula, xmin & xmax, & optionally the unit, eg:
    --mass 'B mass' lab0_M 5200 5800 MeV --decaytime 'B decay time' 'lab0_TAU * 1000.' 0. 10. ps'''

    import argparse
    from argparse import ArgumentParser
    
    argparser = ArgumentParser()
    argparser.add_argument('--inputfiles', nargs = '+', help = 'Name of the input file(s).')
    argparser.add_argument('--inputtree', help = 'Name of the TTree in the input file.')
    argparser.add_argument('--outputfile', help = 'Name of the output file.')
    argparser.add_argument('--datasetname', nargs = '?', default = 'dataset', help = 'Name of the RooDataSet to be made.')
    argparser.add_argument('--datasettitle', nargs = '?', default = 'dataset', help = 'Title of the RooDataSet to be made.')
    argparser.add_argument('--selection', nargs = '?', default = '', help = 'Selection to apply to the TTree.')
    argparser.add_argument('--nentries', nargs = '?', type = long, default = -1, 
                           help = 'Number of entries to read from the TTree')
    argparser.add_argument('--friendfiles', nargs = '*', help = 'Input files for the friend TTree.')
    argparser.add_argument('--friendtree', nargs = '?', default = None, help = 'Name of the friend TTree')
    argparser.add_argument('--ignorecompilefails', action = 'store_true',
                           help = 'Ignore variables that don\'t compile with the given TTree')
    argparser.add_argument('--weightvarname', nargs = '?', default = None, help = 'Name of the weight variable.')
    
    args, remainder = argparser.parse_known_args()
    variableslists = {}
    for arg in remainder :
        if arg.startswith('--') :
            varargs = []
            variableslists[arg[2:]] = varargs
            continue
        varargs.append(arg)
    argnames = 'title', 'formula', 'xmin', 'xmax', 'unit'
    variables = {}
    for var, varargs in variableslists.items() :
        if not len(varargs) in (4, 5) :
            err = '''Invalid number of arguments for variable {0!r}: {1!r}
Arguments should be the title, formula, xmin & xmax, & optionally the unit, eg:
--mass 'B mass' lab0_M 5200 5800 MeV --decaytime 'B decay time' 'lab0_TAU * 1000.' 0. 10. ps'''.format(var, varargs)
            raise ValueError(err)
        try :
            varargs[2] = float(varargs[2])
            varargs[3] = float(varargs[3])
        except :
            err = '''Can't convert ranges to float for variable {0!r}: {1!r} {2!r}!'''\
                .format(var, varargs[2], varargs[3])
            raise ValueError(err)
        variables[var] = dict(zip(argnames, varargs))
    
    tree = make_chain(args.inputtree, *args.inputfiles)
    if args.friendtree :
        friendtree = make_chain(args.friendtree, *args.friendfiles)
        tree.AddFriend(friendtree)

    fout = ROOT.TFile.Open(args.outputfile, 'recreate')
    dataset = make_roodataset(dataname = args.datasetname, datatitle = args.datasettitle, tree = tree,
                              nentries = args.nentries, selection = args.selection, 
                              ignorecompilefails = args.ignorecompilefails, weightvarname = args.weightvarname,
                              **variables)
    dataset.Write()
    fout.Close()

if __name__ == '__main__' :
    main()
