'''Functions for working with TTrees.'''

import ROOT

def make_chain(treename, *fnames) :
    '''Make a TChain from a tree name and a list of file names.'''
    chain = ROOT.TChain(treename)
    for fname in fnames :
        chain.Add(fname)
    return chain

def identifier(tree, i, *branches) :
    '''Get an identifier for entry i in the tree using the given branch names.'''
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

def merge_trees(outputfile, tree1, tree2, *trees) :
    '''Merge the given TTrees into a singla tree with all the branches and write it to the given file.'''
    outputfile.cd()
    trees = (tree2,) + trees
    outputtree = tree1.CopyTree("")
    for tree in trees :
        cptree = tree.CopyTree("")
        for branch in cptree.GetListOfBranches() :
            branch.SetTree(outputtree)
            outputtree.GetListOfBranches().Add(branch)
            outputtree.GetListOfLeaves().Add(branch.GetLeaf(branch.GetName()))
            cptree.GetListOfBranches().Remove(branch)
    outputtree.Write()

def merge_trees_to_file(outputfname, tree1Names, tree2Names, *treeNames) :
    '''Create the file then merge the TTrees into it.'''
    outfile = TFile.Open(outputfname, 'recreate')
    trees = []
    files = []
    for fname, treename in (tree1Names, tree2Names) + treeNames :
        f = TFile.Open(fname)
        trees.append(f.Get(treename))
        files.append(f)
    merge_trees(outfile, *trees)
    for f in files :
        f.Close()
    outfile.Close()

class TreeFormula(object) :
    '''Wrapper for TTreeFormula, so it can just be called and return the value of the formula.
    Works for TTrees and TChains.'''

    chainformulae = {}

    def __init__(self, name, formula, tree) :
        self.form = ROOT.TTreeFormula(name, formula, tree)
        if isinstance(tree, ROOT.TChain) :
            chainid = id(tree)
            if not chainid in TreeFormula.chainformulae :
                formarr = ROOT.TObjArray()
                TreeFormula.chainformulae[chainid] = formarr
                tree.SetNotify(formarr)
            else :
                formarr = TreeFormula.chainformulae[chainid]
            formarr.Add(self.form)

    def __call__(self, tree = None) :
        self.form.GetNdata()
        return self.form.EvalInstance()        

