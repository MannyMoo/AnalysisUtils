'''Functions for working with TTrees.'''

import ROOT, pprint, re, random, string
from array import array

def random_string(n = 6, chars = string.ascii_uppercase + string.ascii_lowercase) :
    '''Generate a random string of length n.'''
    return ''.join(random.choice(chars) for _ in xrange(n))

def is_tfile_ok(tfile) :
    '''Check if a TFile is OK (not a zombie and was closed properly).'''
    close = False
    if isinstance(tfile, str) :
        tfile = ROOT.TFile.Open(tfile)
        close = True
    ok = (None != tfile and not tfile.IsZombie() and not tfile.TestBit(ROOT.TFile.kRecovered))
    if close and tfile and not tfile.IsZombie() :
        tfile.Close()
    return ok

def make_chain(treename, *fnames, **kwargs) :
    '''Make a TChain from a tree name and a list of file names.'''
    Chain = kwargs.get('Class', ROOT.TChain)
    chain = Chain(treename)
    for fname in fnames :
        chain.Add(fname)
    return chain

def set_prefix_aliases(tree, aliases) :
    '''Scan over branches in the tree and if they start with one of the keys in 'aliases',
    create an alias with that key replaced by the corresponding value in 'aliases'.
    Only the first matching key is replaced, and only at the start of the string.
    This allows you to easily work with TTrees with different name prefixes.'''
    for branch in tree.GetListOfBranches() :
        newname = branch.GetName()
        changed = False
        for name, alias in aliases.items() :
            if newname.startswith(name) :
                #print name, alias, newname
                newname = alias + newname[len(name):]
                changed = True
                break
        #print newname, branch.GetName()
        #print
        if changed :
            tree.SetAlias(newname, branch.GetName())

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
    in 'branches' to match entries between the two. If an entry in inputtree doesn't have a 
    matching entry in extratree all the extra branches are filled with -999999.'''

    print 'Get entry identifiers from tree', extratree.GetName()
    # This has the disadvantage of requiring all the identifiers to be in memory.
    extramap = {identifier(extratree, i, *branches) : i for i in xrange(extratree.GetEntries())}
    if len(extramap) != extratree.GetEntries() :
        raise ValueError('Identifiers aren\'t unique! Using branches {0!r} gives {1} unique \
identifiers out of {2} entries.'.format(branches, len(extramap), extratree.GetEntries()))
    if isinstance(outputfile, str) :
        outputfile = ROOT.TFile.Open(outputfile, 'recreate')
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
        if branchtype in 'os' :
            branchtype = 'i'
        leaf = extratree.GetLeaf(branch.GetName())
        leaflen = leaf.GetLen()
        if leaf.GetLeafCount() :
            leaflen = leaf.GetLeafCount().GetMaximum()
        try :
            vals = array(branchtype, [0] * leaflen)
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
            unmatchedids.append((i, ident))
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
    outfile = ROOT.TFile.Open(outputfname, 'recreate')
    trees = []
    files = []
    for fname, treename in (tree1Names, tree2Names) + treeNames :
        f = ROOT.TFile.Open(fname)
        trees.append(f.Get(treename))
        files.append(f)
    merge_trees(outfile, *trees)
    for f in files :
        f.Close()
    outfile.Close()

def check_formula_compiles(formula, tree) :
    '''Check if the given forumla compiles on the given tree.'''
    return ROOT.TTreeFormula(formula, formula, tree).Compile() == 0

class TreeFormula(object) :
    '''Wrapper for TTreeFormula, so it can just be called and return the value of the formula.
    Works for TTrees and TChains.'''

    chainformulae = {}
    
    def __init__(self, name, formula, tree) :
        self.form = ROOT.TTreeFormula(name, formula, tree)
        # Calling Compile sometimes breaks the TTreeFormula, for reasons unknown, so
        # use a disposable instance to check compilation.
        self.ok = check_formula_compiles(formula, tree)
        if isinstance(tree, ROOT.TChain) :
            chainid = id(tree)
            if not chainid in TreeFormula.chainformulae :
                formarr = ROOT.TObjArray()
                TreeFormula.chainformulae[chainid] = formarr
                tree.SetNotify(formarr)
            else :
                formarr = TreeFormula.chainformulae[chainid]
            formarr.Add(self.form)

    def is_ok(self) :
        '''Check that the formula compiles.'''
        return self.ok

    def __call__(self, tree = None) :
        '''Evaluate and return the formula.'''
        self.form.GetNdata()
        return self.form.EvalInstance()        

    def __del__(self) :
        '''For TChains, remove the TTreeFormula from the TChain's notify list.
        Delete the notify list if it's empty.'''
        treeid = id(self.form.GetTree())
        if treeid in TreeFormula.chainformulae :
            arr = TreeFormula.chainformulae[treeid]
            arr.Remove(self.form)
            if arr.GetSize() == 0 :
                self.form.GetTree().SetNotify(None)
                del TreeFormula.chainformulae[treeid]

    def used_leaves(self) :
        '''Get the names of all the branches used by the formula.'''

        return [self.form.GetLeaf(i).GetName() for i in xrange(self.form.GetNcodes())]

def make_treeformula(name, formula, tree, randlen = 0):
    '''Make a TreeFormula from the given formula if it's a string, otherwise
    assume it's some other callable and return it as it is.'''
    # Assume it's some callable object.
    if not isinstance(formula, str):
        return formula
    if randlen > 0:
        name += '_' + random_string(randlen)
    return TreeFormula(name, formula, tree)

class TreeFormulaList(object) :
    '''A list of TreeFormulas.'''

    __slots__ = ('forms',)

    def __init__(self, tree, formula1, *formulae) :
        '''Takes the TTree and the formulae.'''
        # Could use make_treeformula, but it uses other functions from TreeFormula
        # so can't necessarily accept any arbitrary callable.
        self.forms = tuple(TreeFormula(form, form, tree) for form in (formula1,) + formulae)

    def is_ok(self) :
        '''Check that all formulae compile.'''
        return all(f.ok for f in self.forms)

    def __call__(self, tree = None) :
        '''Get the formula values as a list.'''
        return [f() for f in self.forms]

    def used_leaves(self) :
        '''Get the names of all leaves used by all the formulae.'''
        leaves = set()
        for form in self.forms :
            leaves.update(form.used_leaves())
        return list(leaves)

class TreePVector(TreeFormulaList) :
    '''Momentum 4-vector for a given particle name.'''
    
    __slots__ = ('forms',)

    def __init__(self, tree, partname, pform = '{partname}_P{comp}') :
        '''Takes the particle name and the tree. The branches used will be 
        pform.format(partname = partname, comp = comp) for comp in XYZE. For true momenta, you can use
        pname = '{partname}_TRUEP_{comp}'.'''
        TreeFormulaList.__init__(self, tree, *[pform.format(partname = partname, comp = comp) for comp in 'XZYE'])
        
    def vector(self, tree = None) :
        '''Get the momentum 4-vector as a TLorentzVector.'''
        return ROOT.TLorentzVector(*self())

def rename_branches(tree, *replacements) :
    '''Rename branches in a TTree. 'replacements' should be pairs of (pattern, replacement).
    If 'pattern' is in the branch name, it's replaced with 'replacement'. It just does a 
    simple search and replace (not, eg, regex).'''

    for branch in tree.GetListOfBranches() :
        for pattern, replacement in replacements :
            if not pattern in branch.GetName() :
                continue
            leaf = tree.GetLeaf(branch.GetName())
            for thing in branch, leaf :
                thing.SetNameTitle(thing.GetName().replace(pattern, replacement),
                                   thing.GetTitle().replace(pattern, replacement))

def has_active_branches(tree) :
    '''Check if the TTree has any active branches.'''
    return any(not branch.TestBit(ROOT.kDoNotProcess) for branch in tree.GetListOfBranches())

def copy_tree(tree, selection = '', nentries = -1, keepbranches = (),
              removebranches = (), rename = None, write = False, returnfriends = False,
              fname = None, foption = 'recreate') :
    '''Copy the given TTree, optionally applying the given selection, or keeping nentries 
    entries. 'keepbranches' and 'removebranches' can be iterables of string regexes 
    that determine which branches are kept or removed. If both are given, the branches
    to be kept are applied first. 'rename' can be a function that returns the name to
    give the copied tree when passed the old tree's name. If write = True then the 
    copied tree is written to the current directory. If the TTree has friends, these
    will also be copied and the copies added as friends to the copy of the original
    TTree. If you want the copied friends to be returned as well, use 
    returnfrieds = True. Then the copied TTree and a list of its copied friends
    will be returned (the list will be empty if the TTree has no friends).'''

    tree.SetBranchStatus('*', True)
    # Need to use an EventList rather than passing the string to TTree::CopyTree
    # so that we can copy friend trees that don't contain all the required
    # branches for the selection.
    if selection and isinstance(selection, str) :
        selection = get_event_list(tree, selection)
        selection.SetDirectory(None)
    if selection :
        prevlist = tree.GetEventList()
        tree.SetEventList(selection)

    if keepbranches :
        for branch in tree.GetListOfBranches() :
            if not any(re.search(pattern, branch.GetName()) for pattern in keepbranches) :
                branch.SetStatus(False)
    if removebranches :
        for branch in tree.GetListOfBranches() :
            if any(re.search(pattern, branch.GetName()) for pattern in removebranches) :
                branch.SetStatus(False)
    
    if fname:
        fout = ROOT.TFile.Open(fname, foption)
    if nentries > 0 :
        treecopy = tree.CopyTree('', '', int(nentries))
    else :
        treecopy = tree.CopyTree('')

    if rename :
        treecopy.SetName(rename(tree.GetName()))

    if selection :
        tree.SetEventList(prevlist)

    tree.SetBranchStatus('*', True)

    copyfriends = []
    if tree.GetListOfFriends() :
        # Accessing the list of friends in python adds it to the list of ROOT objects to cleanup,
        # but it's owned by the TTree, causing a double delete. So remove it from the cleanup
        # list.
        treecopy.GetListOfFriends().Clear()
        treecopy.GetListOfFriends().SetBit(ROOT.kMustCleanup, False)
        friends = [elm.GetTree() for elm in tree.GetListOfFriends()]
        for friend in friends :
            copyfriend, copyfriendfriends = \
                copy_tree(friend,
                          selection = selection,
                          nentries = nentries,
                          keepbranches = keepbranches,
                          removebranches = removebranches,
                          write = write,
                          rename = rename,
                          returnfriends = True)
            if not copyfriend :
                continue
            copyfriends.append(copyfriend)
            copyfriends += copyfriendfriends
            treecopy.AddFriend(copyfriend)

    if write :
        treecopy.Write()

    # Close the output file then retrieve the trees as TChains.
    if fname:
        name = treecopy.GetName()
        friendnames = [t.GetName() for t in copyfriends]
        fout.Close()
        treecopy = ROOT.TChain(name)
        copyfriends = [ROOT.TChain(n) for n in friendnames]
        for t in [treecopy] + copyfriends:
            t.Add(fname)
            
    if returnfriends :
        return treecopy, copyfriends

    return treecopy

def tree_loop(tree, selection = None, getter = (lambda t, i : t.LoadTree(i))) :
    '''Iterator over a TTree or TChain, calling getter(tree, i) for each entry
    (default to call tree.LoadTree(i)) and yielding i, optionally only for 
    entries passing the selection. The selection can either be a string or a 
    TEventList.'''
    
    if not selection :
        for i in xrange(tree.GetEntries()) :
            getter(tree, i)
            yield i
    else :
        if isinstance(selection, str) :
            sellist = get_event_list(tree, selection = selection)
        else :
            sellist = selection
        for i in xrange(sellist.GetN()) :
            i = sellist.GetEntry(i)
            getter(tree, i)
            yield i

def tree_iter(tree, formula, selection = None) :
    '''Iterator over a TTree, returning the formula value, optionally only for 
    entries satisfying the selection.'''
    form = make_treeformula('val', formula, tree, 9)
    else:
        form = formula
    for i in tree_loop(tree, selection) :
        yield form()

def tree_mean(tree, formula, selection = None, weight = None) :
    '''Mean of the formula over the TTree, optionally only for entries passing
    the selection.'''
    n = 0
    tot = 0.
    totsq = 0.
    if not weight :
        for val in tree_iter(tree, formula, selection) :
            n += 1
            tot += val
            totsq += val**2.
    else :
        valform = make_treeformula('val', formula, tree, 9)
        weightform = make_treeformula('weight', weight, tree, 9)
        sumw2 = 0.
        ncand = 0
        for i in tree_loop(tree, selection) :
            weight = weightform()
            val = valform()
            n += weight
            tot += val * weight
            totsq += val**2. * weight
            sumw2 += weight**2.
            ncand += 1
    mean = tot/n
    meansq = totsq/n
    err = ((meansq - mean**2)/n)**.5
    # Scale the error to account for the weights.
    if weight :
        neff = n**2/sumw2
        err *= (ncand/neff)**.5
    return mean, err

def get_event_list(tree, selection, setlist = False, listname = '') :
    '''Get the TEventList of entries that pass the selection. If setlist = True, the TTree's
    event list is set to this.'''

    if not check_formula_compiles(selection, tree):
        raise ValueError('Failed to compile selection {1!r} on TTree {2!r}'.format(selection, tree.GetName()))

    if not listname :
        listname = (tree.GetName() + '_sellist_' + random_string()).replace('/', '_')
    evtlist = ROOT.TEventList(listname)
    # TTree::Draw resets the Notify list for TChains, so set it back after.
    notify = tree.GetNotify() if hasattr(tree, 'GetNotify') else None
    tree.Draw('>>' + evtlist.GetName(), selection)
    if setlist :
        tree.SetEventList(evtlist)
    if notify :
        tree.SetNotify(notify)
    return evtlist

def get_unique_events(tree, listname = None, seedoffset = 0, setlist = False,
                      checkbranches = ('eventNumber', 'runNumber'), selection = None) :
    '''Get one entry per event from the given tree. When there's more than one with the same
    event number, events are picked at random using 
    int(str(eventNumber) + str(runNumber)) + seedoffset as seed. Note that the algorithm
    assumes that candidates in the same event are in consecutive entries in the TTree.'''

    nentries = tree.GetEntries()
    checker = TreeFormulaList(tree, *checkbranches)
    rndm = ROOT.TRandom3()
    if not listname :
        listname = tree.GetName() + '_uniqueevtlist_' + random_string()
    evtlist = ROOT.TEventList(listname)
    treeloop = tree_loop(tree, selection)
    while True :
        try :
            ievt = treeloop.next()
            checkvals = checker()
            nextvals = list(checkvals)
            evts = []
            while nextvals == checkvals :
                evts.append(ievt)
                ievt = treeloop.next()
                nextvals = checker()
            if len(evts) == 1 :
                evtlist.Enter(evts[0])
                continue
            rndm.SetSeed(long(''.join(map(lambda v : str(int(v)), checkvals))) + seedoffset)
            ival = int(rndm.Rndm()*len(evts))
            evtlist.Enter(evts[ival])
        except StopIteration :
            break
    if setlist :
        tree.SetEventList(evtlist)
    return evtlist

class TreeBranchAdder(object) :
    '''Add a branch to a TTree.'''

    def __init__(self, tree, name, function, type = 'f', length = 1, maxlength = 1, args = (), kwargs = {},
                 filllength = True) :
        '''tree: the TTree to add the branch to.
        name: name of the branch.
        function: must return a list of values for the branch when called. It will be passed *args and **kwargs.
        type: data type of the branch.
        length: length of the branch. If a string, the branch is variable length and the string is used as
          the name of the length branch.
        maxlength: maximum length of the branch.
        args: args to be passed to function.
        kwargs: kwrags to be passed to function.
        filllength: whether to fill the length branch or not.
        '''

        self.tree = tree
        self.name = name
        self.values = array(type, [0] * maxlength)
        self.type = type
        if isinstance(length, str) and filllength:
            self.length = TreeBranchAdder(tree, length, function = lambda : len(self.values), type = 'i')
            self.set_length = lambda : self.length.set_value()
            self.fill_length = lambda : self.length.fill()
        else :
            self.length = length
            self.set_length = lambda : True
            self.fill_length = lambda : True
        self.maxlength = maxlength
        self.function = function
        self.args = tuple(args)
        self.kwargs = dict(kwargs)
        self.branch = tree.Branch(self.name, self.values,
                                  '{0}[{1}]/{2}'.format(self.name, self.length, self.type.upper()))

    @staticmethod
    def copy_branch(tree, branchname, treeout, function, args = (), kwargs = {}, filllength = True) :
        br = tree.GetBranch(branchname)
        br.GetEntry(0)
        leaf = tree.GetLeaf(branchname)
        lenleaf = leaf.GetLeafCount()
        if lenleaf : 
            maxlen = lenleaf.GetMaximum()
            lenleaf = lenleaf.GetName()
        else :
            lenleaf = leaf.GetLen()
            maxlen = lenleaf
        leaftype = leaf.GetTypeName()[0].lower()
        return TreeBranchAdder(treeout, branchname, function, type = leaftype, args = args, kwargs = kwargs, 
                               maxlength = maxlen, length = lenleaf, filllength = filllength)

    def set_value(self) :
        '''Set the values of the branch array, and length branch if appropriate.'''
        vals = self.function(*self.args, **self.kwargs)[:self.maxlength]
        del self.values[:]
        self.values.fromlist(vals)
        self.set_length()

    def fill(self) :
        '''Fill the branch, and the length branch if appropriate.'''
        self.branch.Fill()
        self.fill_length()

def search_branches(tree, pattern1, *patterns) :
    '''Return branch names in the given TTree that match any of the given patterns.'''
    patterns = (pattern1,) + patterns
    return filter(lambda name : any(re.search(pat, name) for pat in patterns),
                  (br.GetName() for br in tree.GetListOfBranches()))
