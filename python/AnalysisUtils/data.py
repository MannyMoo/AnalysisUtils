'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

import os, ROOT, pprint
from CharmBaryonLifetimes.makeroodataset import make_roodataset
from CharmBaryonLifetimes.variables import variables
from array import array

datadir = os.environ.get('ANALYSISUTILSDATADIR', 
                         'root://eoslhcb.cern.ch//eos/lhcb/user/u/user/data/')

def make_chain(treename, *fnames) :
    '''Make a TChain from a tree name and a list of file names.'''
    chain = ROOT.TChain(treename)
    for fname in fnames :
        chain.Add(fname)
    return chain

# All the TTree datasets, the tree names and file names (any number of file names can be given).
datapaths = {'LTUNB_Lc_2015' : ('XcTopKpiTuple/DecayTree', os.path.join(datadir, 'Lc_2015.root')),
             }

def get_data(name) :
    '''Get the dataset of the given name.'''
    try :
        return make_chain(*datapaths[name])
    except KeyError :
        raise ValueError('Unknown data type: ' + repr(name))

def dataset_file_name(dataname) :
    '''Get the name of the file containing the RooDataset corresponding to the given
    dataset name.'''
    return os.path.join(os.path.dirname(datapaths[dataname][1]), dataname + '_Dataset.root')

def get_dataset(dataname, varnames = ('mass', 'decaytime', 'XcIPX', 'XcIPY'), update = False) :
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

# Define getter methods for every TTree dataset and corresponding RooDataSet.
for name in datapaths :
    globals()[name] = eval('lambda : get_data({0!r})'.format(name))
    globals()[name + '_Dataset'] = eval('lambda : get_dataset({0!r})'.format(name))

def identifier(tree, i, *branches) :
    vals = []
    for branch in branches :
        tree.GetBranch(branch).GetEntry(i)
        branchvals = []
        leaf = tree.GetLeaf(branch)
        for j in xrange(leaf.GetLen()) :
            branchvals.append(leaf.GetValue(j))
        vals.append((branch, branchvals))
    return repr(vals)

def match_trees(inputtree, extratree, outputfile, *branches) :
    '''Add extra branches in extratree to a copy of inputtree, using the values of the branches 
    in 'branches' to match entries between the two. Every entry in inputtree must have a 
    corresponding entry in extratree.

    Doesn't currently work for array type branches with variable lengths, but could be made to do so.'''

    print 'Get entry identifiers from tree', extratree.GetName()
    # This has the disadvantage of requiring all the identifiers to be in memory.
    extramap = {identifier(extratree, i, *branches) : i for i in xrange(extratree.GetEntries())}
    if isinstance(outputfile, str) :
        outputfile = ROOT.TFile.Open(outputfname, 'recreate')
    outputfile.cd()
    print 'Copy tree', inputtree.GetName()
    outputtree = inputtree.CopyTree('')
    inputtreebranches = tuple(br.GetName() for br in inputtree.GetListOfBranches())
    newbranches = []
    print 'Adding extra branches'
    for branch in extratree.GetListOfBranches() :
        if branch.GetName() in inputtreebranches :
            continue
        branchtype = branch.GetTitle().split('/')[-1].lower()
        if branchtype == 'o' :
            branchtype = 'i'
        leaf = extratree.GetLeaf(branch.GetName())
        try :
            vals = array(branchtype, [0] * leaf.GetLen())
        except ValueError :
            print branch.GetTitle()
            raise
        newbranch = outputtree.Branch(branch.GetName(), vals, branch.GetTitle())
        newbranches.append((newbranch, vals, branch, leaf))
    types = {'i' : int,
             'f' : float,
             'd' : float}
    nunmatched = 0
    unmatchedids = []
    for i in xrange(outputtree.GetEntries()) :
        ident = identifier(inputtree, i, *branches)
        try :
            j = extramap[ident]
            for newbranch, vals, branch, leaf in newbranches :
                branch.GetEntry(j)
                for k in xrange(leaf.GetLen()) :
                    vals[k] = types[vals.typecode](leaf.GetValue(k))
                newbranch.Fill()
        except KeyError :
            nunmatched += 1
            unmatchedids.append(ident)
            for newbranch, vals, branch, leaf in newbranches :
                for k in xrange(leaf.GetLen()) :
                    vals[k] = types[vals.typecode](-999999.)
                newbranch.Fill()
    print 'N. unmatched', nunmatched, '/', outputtree.GetEntries()
    if unmatchedids :
        with open('unmatched-ids.txt', 'w') as f :
            f.write(pprint.pformat(unmatchedids) + '\n')
    outputtree.Write()
    outputfile.Close()
