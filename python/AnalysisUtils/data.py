'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

import os, ROOT, pprint
from AnalysisUtils.makeroodataset import make_roodataset
from AnalysisUtils.treeutils import make_chain
from array import array

def get_data(datapaths, name) :
    '''Get the dataset of the given name.'''
    try :
        return make_chain(*datapaths[name])
    except KeyError :
        raise ValueError('Unknown data type: ' + repr(name))

def dataset_file_name(datapaths, dataname) :
    '''Get the name of the file containing the RooDataset corresponding to the given
    dataset name.'''
    return os.path.join(os.path.dirname(datapaths[dataname][1]), dataname + '_Dataset.root')

def get_dataset(dataname, variables, varnames, update = False) :
    '''Get the RooDataSet of the given name. It's created/updated on demand. varnames is the 
    set of variables to be included in the RooDataSet. They must correspond to those defined 
    in the variables module. If the list of varnames changes or if update = True the 
    RooDataSet will be recreated.'''
    if not update :
        fout = ROOT.TFile.Open(dataset_file_name(dataname))
        if fout :
            dataset = fout.Get(dataname)
            cand = dataset.get(0)
            if set(varnames) == set(cand.contentsString().split(',')) :
                fout.Close()
                return dataset
            fout.Close()

    print 'Making RooDataSet for', dataname
    tree = get_data(dataname)
    dataset = make_roodataset(dataname, dataname, tree,
                              **dict((var, variables[var]) for var in varnames))

    fname = dataset_file_name(dataname)
    print 'Saving to', fname
    fout = ROOT.TFile.Open(fname, 'recreate')
    dataset.Write()
    fout.Close()
    return dataset

def make_getters(namespace, datapaths) :
    '''Define getter methods for every TTree dataset and corresponding RooDataSet.'''
    for name in datapaths :
        namespace[name] = eval('lambda : get_data({0!r})'.format(name))
        namespace[name + '_Dataset'] = eval('lambda : get_dataset({0!r})'.format(name))
