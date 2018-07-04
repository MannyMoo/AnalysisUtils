'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

import os, ROOT, pprint
from AnalysisUtils.makeroodataset import make_roodataset
from AnalysisUtils.treeutils import make_chain, set_prefix_aliases, check_formula_compiles
from array import array

class DataLibrary(object) :
    '''Contains info on datasets and functions to retrieve them.'''

    class DataGetter(object) :
        '''Simple wrapper for dynamic construction of callables to retrieve datasets.'''
        def __init__(self, method, *args) :
            self.method = method
            self.args = args
        
        def __call__(self) :
            return self.method(*self.args)

    def __init__(self, datapaths, variables, ignorecompilefails = False, selection = '', varnames = ()) :
        self.datapaths = datapaths
        self.variables = variables
        self.varnames = varnames
        self.selection = selection
        self.ignorecompilefails = ignorecompilefails
        self.make_getters()

    def _getattr(self, tree, attr) :
        '''Get an attr from the tree if it has it, else return the DataLibrary's one.'''
        if hasattr(tree, attr) :
            return getattr(tree, attr)
        return getattr(self, attr)

    def _variables(self, tree) :
        '''Get the variables dict of the TTree if it has one, else return the default dict.'''
        return self._getattr(tree, 'variables')

    def _selection(self, tree) :
        '''Get the selection of the TTree if it has one, else return the default selection.'''
        return self._getattr(tree, 'selection')

    def get_data(self, name) :
        '''Get the dataset of the given name.'''
        try :
            info = self.datapaths[name]
            if isinstance(info, dict) :
                t = make_chain(info['tree'], *info['files'])
                aliases = info.get('aliases', {})
                set_prefix_aliases(t, **aliases)
                if 'variables' in info :
                    t.variables = dict(self.variables)
                    t.variables.update(info['variables'])
                if 'selection' in info :
                    t.selection = info['selection']
                return t
            else :
                return make_chain(*self.datapaths[name])
        except KeyError :
            raise ValueError('Unknown data type: ' + repr(name))

    def dataset_file_name(self, dataname) :
        '''Get the name of the file containing the RooDataset corresponding to the given
        dataset name.'''
        if isinstance(self.datapaths[dataname], dict) :
            if 'datasetdir' in self.datapaths[dataname] :
                dirname = self.datapaths[dataname]['datasetdir']
            else :
                dirname = os.path.dirname(self.datapaths[dataname]['files'][0])
        else :
            dirname = os.path.dirname(self.datapaths[dataname][1])
        return os.path.join(dirname, dataname + '_Dataset.root')

    def get_dataset(self, dataname, varnames = None, update = False) :
        '''Get the RooDataSet of the given name. It's created/updated on demand. varnames is the 
        set of variables to be included in the RooDataSet. They must correspond to those defined 
        in the variables module. If the list of varnames changes or if update = True the 
        RooDataSet will be recreated.'''

        tree = self.get_data(dataname)

        if not varnames :
            varnames = self.varnames
        if not update :
            fout = ROOT.TFile.Open(self.dataset_file_name(dataname))
            if fout :
                dataset = fout.Get(dataname)
                cand = dataset.get(0)
                if self.ignorecompilefails :
                    checkvarnames = filter(lambda name : check_formula_compiles(self.variables[name]['formula'],
                                                                                tree),
                                           varnames)
                else :
                    checkvarnames = varnames
                if dataset and cand and set(checkvarnames) == set(cand.contentsString().split(',')) :
                    fout.Close()
                    return dataset
                fout.Close()

        print 'Making RooDataSet for', dataname
        variables = self._variables(tree)
        dataset = make_roodataset(dataname, dataname, tree,
                                  ignorecompilefails = self.ignorecompilefails,
                                  selection = self._selection(tree),
                                  **dict((var, variables[var]) for var in varnames))

        fname = self.dataset_file_name(dataname)
        print 'Saving to', fname
        fout = ROOT.TFile.Open(fname, 'recreate')
        dataset.Write()
        fout.Close()
        return dataset

    def make_getters(self) :
        '''Define getter methods for every TTree dataset and corresponding RooDataSet.'''
        for name in self.datapaths :
            setattr(self, name, DataLibrary.DataGetter(self.get_data, name))
            setattr(self, name + '_Dataset', DataLibrary.DataGetter(self.get_dataset, name))

    def _form_and_range(self, tree, variable, xmin, xmax) :
        '''Get the variable formula and range if it's in the dict of variables.'''
        variables = self._variables(tree)
        if variable in variables :
            form = variables[variable]['formula']
            xmin = xmin if xmin != None else variables[variable]['xmin']
            xmax = xmax if xmax != None else variables[variable]['xmax']
        else :
            form = variable
            if xmin == None or xmax == None :
                raise ValueError('Must give xmin and xmax for variables not in the known variables!')
        return form, xmin, xmax

    def draw(self, tree, variable, hname = None, nbins = None, xmin = None, xmax = None, selection = None,
             variableY = None, nbinsY = None, ymin = None, ymax = None, drawopt = '') :
        '''Make a histogram of a variable. If 'tree' is a string, the dataset with the corresponding name
        is retrieved, else it's expected to be a TTree. If 'variable' is the name of a variable in the internal
        dict of variables, then its formula is taken from there, else it's expected to be a formula understood
        by the TTree. Similarly for xmin & xmax. Default nbins is 100. The default selection is the internal
        selection given to the constructor.'''

        if isinstance(tree, str) :
            tree = self.get_data(tree)
        nbins = nbins if nbins else 100
        if not hname :
            if variableY :
                hname = variableY + '_vs_' + variable
            else :
                hname = variable
        if not selection :
            selection = self._selection(tree)
        form, xmin, xmax = self._form_and_range(tree, variable, xmin, xmax)
        if not variableY :
            h = ROOT.TH1F(hname, '', nbins, xmin, xmax)
            tree.Draw('{form} >> {hname}'.format(**locals()), selection, drawopt)
            return h
        formY, ymin, ymax = self._form_and_range(tree, variableY, ymin, ymax)
        if None == nbinsY :
            nbinsY = nbins
        h = ROOT.TH2F(hname, '', nbins, xmin, xmax, nbinsY, ymin, ymax)
        tree.Draw('{formY} : {form} >> {hname}'.format(**locals()), selection, drawopt)
        return h

