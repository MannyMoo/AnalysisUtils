'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

import os, ROOT, pprint
from AnalysisUtils.makeroodataset import make_roodataset
from AnalysisUtils.treeutils import make_chain
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

    def __init__(self, datapaths, variables, ignorecompilefails = False, varnames = ()) :
        self.datapaths = datapaths
        self.variables = variables
        self.varnames = varnames
        self.make_getters()

    def get_data(self, name) :
        '''Get the dataset of the given name.'''
        try :
            return make_chain(*self.datapaths[name])
        except KeyError :
            raise ValueError('Unknown data type: ' + repr(name))

    def dataset_file_name(self, dataname) :
        '''Get the name of the file containing the RooDataset corresponding to the given
        dataset name.'''
        return os.path.join(os.path.dirname(self.datapaths[dataname][1]), dataname + '_Dataset.root')

    def get_dataset(self, dataname, varnames = None, update = False) :
        '''Get the RooDataSet of the given name. It's created/updated on demand. varnames is the 
        set of variables to be included in the RooDataSet. They must correspond to those defined 
        in the variables module. If the list of varnames changes or if update = True the 
        RooDataSet will be recreated.'''
        if not varnames :
            varnames = self.varnames
        if not update :
            fout = ROOT.TFile.Open(self.dataset_file_name(dataname))
            if fout :
                dataset = fout.Get(dataname)
                cand = dataset.get(0)
                if set(varnames) == set(cand.contentsString().split(',')) :
                    fout.Close()
                    return dataset
                fout.Close()

        print 'Making RooDataSet for', dataname
        tree = self.get_data(dataname)
        dataset = make_roodataset(dataname, dataname, tree,
                                  ignorecompilefails = self.ignorecompilefails,
                                  **dict((var, self.variables[var]) for var in varnames))

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
