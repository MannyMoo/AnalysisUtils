'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

from __future__ import print_function
from AnalysisUtils.RooFit import RooFit
import os, ROOT, pprint, cppyy, glob, re, multiprocessing, datetime, sys
from AnalysisUtils.makeroodataset import make_roodataset, make_roodatahist
from AnalysisUtils.treeutils import make_chain, set_prefix_aliases, check_formula_compiles, is_tfile_ok, copy_tree,\
    TreeBranchAdder, tree_loop, TreeFormula, TreeFormulaList, tree_mean, tree_iter
from array import array
from copy import deepcopy
from multiprocessing import Pool
from AnalysisUtils.stringformula import NamedFormula, NamedFormulae, StringFormula
from AnalysisUtils.datacache import DataCache
from AnalysisUtils.selection import AND, OR, product

def _is_ok(tree, fout, selection):
    '''Check if a TTree has been copied OK to the output file.'''
    if not is_tfile_ok(fout):
        return False
    fout = ROOT.TFile.Open(fout)
    cptree = fout.Get(os.path.split(tree.GetName())[1])
    if not cptree:
        return False
    nentries = tree.GetEntries(selection)
    if cptree.GetEntries() != nentries:
        return False
    return True

def _parallel_filter(tree, ifile, iend, selection, outputdir, outputname, nthreads,
                     zfill, overwrite, ignorefriends):
    '''Filter a single file from a TChain.'''
    if ifile != 0 or iend != tree.nfiles():
        fout = os.path.join(outputdir, outputname + '_{0}_{1}.root')
        fout = fout.format(str(ifile).zfill(zfill), str(iend).zfill(zfill))
        tree = tree.get_subset(ifile, iend, ignorefriends = ignorefriends)
    else:
        fout = os.path.join(outputdir, outputname + '.root')
        tree = tree.clone()
    if not overwrite and _is_ok(tree, fout, selection):
        return True
    cptree = copy_tree(tree = tree, selection = selection,
                       fname = fout, write = True)
    return bool(cptree)

class DataChain(ROOT.TChain):
    '''Wrapper for TChain to add useful functionality, also makes sure that its file gets closed
    when it's deleted.'''

    _ctorargs = ('name', 'tree', 'files', 'variables', 'varnames', 'selection',
                 'datasetdir', 'ignorecompilefails', 'aliases', 'friends', 'addfriends',
                 'ignorefriends', 'sortfiles', 'zombiewarning', 'build', 'ctime')

    def __init__(self, name, tree, files, variables = {}, varnames = (), selection = '',
                 datasetdir = None, ignorecompilefails = False, aliases = {},
                 friends = [], addfriends = True, ignorefriends = [], sortfiles = True,
                 zombiewarning = True, build = True, ctime = None) :
        self.name = name
        self.tree = tree
        if sortfiles:
            self.files = sorted(files)
        else:
            self.files = list(files)
        if not self.files and zombiewarning:
            print('ERROR: constructing DataChain {0}: no files given!'.format(self.name), file = sys.stderr)
        self.variables = NamedFormulae(variables)
        self.varnames = varnames
        self.selection = selection if selection != None else ''
        self.ignorecompilefails = ignorecompilefails
        self.aliases = aliases
        self.friends = {}
        if datasetdir:
            self.datasetdir = datasetdir
        else:
            self.datasetdir = os.path.dirname(self.files[0])
        self.ignorefriends = ignorefriends
        self.initfriends = filter(lambda chain : chain.name not in self.ignorefriends, friends)
        self.addfriends = addfriends
        self.sortfiles = sortfiles
        self.zombiewarning = zombiewarning
        self.build = build
        self.ctime = ctime
        self.loadcode = None

        super(DataChain, self).__init__(tree)
        # Option so it doesn't add files, do aliases, friends, etc, just caches the file info.
        self.built = False
        if not build:
            return
        self._build()

    def _build(self):
        '''Add the files, set aliases, add friends.'''
        if self.built:
            return

        for f in self.files:
            self.Add(f)

        for varname, varinfo in self.variables.items():
            if varname != varinfo['formula']:
                self.SetAlias(varname, varinfo['formula'])

        self.loadcode = self.LoadTree(0)
        if self.is_ok(self.zombiewarning):
            set_prefix_aliases(self, self.aliases)

        for friend in self.initfriends:
            self.AddFriend(friend)

        if self.addfriends:
            self.add_auto_friends()

        self.built = True

        if self.loadcode < 0:
            return

        if not self.ctime:
            self.update_ctime()

    def update_ctime(self):
        '''Update the creation time from the TFiles.'''
        tdir = self.GetFile()
        if not tdir:
            return
        for name in self.tree.split('/'):
            key = tdir.GetKey(name)
            tdir = tdir.Get(name)
        ctime = key.GetDatime()
        self.ctime = datetime.datetime(**{attr : getattr(ctime, 'Get' + attr.capitalize())() for attr in ('year', 'month', 'day', 'hour', 'minute', 'second')})

    def __del__(self):
        '''Closes the TChain's file.'''
        #print('Del', self.name)
        if self.GetFile():
            #print('Close file', self.GetFile().GetName())
            self.GetFile().Close()

    def AddFriend(self, friend, alias = '', warn = False):
        '''Add a friend tree.'''
        super(DataChain, self).AddFriend(friend, alias, warn)
        if not alias:
            alias = friend.name
        self.friends[alias] = friend

    def is_ok(self, warning = True):
        '''Check if we can load the first entry in the chain.'''
        result = self.loadcode
        # Not built.
        if None == result:
            if warning:
                print('ERROR: DataChain.is_ok: dataset', self.name, 'has not been built!',
                      file = sys.stderr)
            return False
        if result >= 0:
            return True
        if warning:
            print('ERROR: DataChain.is_ok: dataset', self.name, 'is a zombie! (error {0})'.format(result),
                  file = sys.stderr)
        return False

    def friends_directory(self):
        '''Get the directory containing friends that will be automatically loaded.'''
        return os.path.join(self.datasetdir, self.name + '_Friends')

    def _ignore(self, friendname, ignorefriends):
        return friendname in ignorefriends or self.name + '_' + friendname in ignorefriends

    def get_auto_friends(self, ignorefriends = [], build = True):
        '''Get friend trees from from the friends directory to be added.'''
        friendsdir = self.friends_directory()
        if not os.path.exists(friendsdir):
            return []
        friends = []
        for friendname in os.listdir(friendsdir):
            if self._ignore(friendname, ignorefriends):
                continue
            files = glob.glob(os.path.join(friendsdir, friendname, '*.root'))
            if not files :
                continue
            fname = os.path.split(files[0])[1]
            # Take the name of the file as the name of the TTree
            treename = fname[:-len('.root')]
            # Check if the file ends with __[0-9]+__, in which case remove it.
            search = re.search('__[0-9]+\__.root$', fname)
            if search:
                treename = treename[:search.start()]
            friendname = self.name + '_' + friendname
            friend = DataChain(friendname, treename, files, variables = self.variables,
                               aliases = self.aliases, ignorefriends = ignorefriends,
                               build = build)
            # False as it will have already given a warning from the constructor.
            if friend.is_ok(False):
                friends.append(friend)
        return friends

    def add_auto_friends(self, build = True):
        '''Add friends automatically from the friends directory.'''
        friends = self.get_auto_friends(self.ignorefriends, build)
        for friend in friends:
            self.AddFriend(friend)

    def friend_file_name(self, friendname, treename, number = None, makedir = False, zfill = 4) :
        '''Get the name of a file that will be automatically added as a friend to this dataset,
        optionally with a number. 'treename' is the name of the TTree it's expected to contain.
        If makedir = True then the directory to hold the file is created.'''
        if None != number :
            fname = treename + '__' + str(number).zfill(zfill) + '__.root'
        else :
            fname = treename + '.root'
        dirname = os.path.join(self.friends_directory(), friendname)
        if makedir and not os.path.exists(dirname) :
            os.makedirs(dirname)
        return os.path.join(dirname, fname)

    def get_ignorefriends_perfile(self, ignorefriends = [], warning = True):
        '''Get friends that should be ignored for per-file operations as they have different n. files.'''
        ignores = []
        for friend in self.friends.values():
            if self._ignore(friend.name, ignorefriends):
                continue
            if len(friend.files) != len(self.files):
                ignores.append(friend.name)
        if ignores and warning:
            print('Warning: skipping friends', ignores, 'of', self.name, 'due to different n. files')
        return ignorefriends + ignores

    def get_subset(self, ifile, iend = None, addfriends = True, ignorefriends = [], ignoreperfile = False):
        '''Get a subset of the chain using a given file index or range of files.'''
        ignorefriends = self.get_ignorefriends_perfile(ignorefriends, not ignoreperfile)
        friends = []
        if addfriends:
            for name, friend in self.friends.items():
                if self._ignore(friend.name, ignorefriends):
                    continue
                friends.append(friend.get_subset(ifile, iend, addfriends, ignorefriends, ignoreperfile))
        if None == iend:
            iend = ifile+1
        files = self.files[ifile:iend]
        return DataChain(name = '{0}_{1}_{2}'.format(self.name, ifile, iend), tree = self.tree, files = files,
                         variables = self.variables, varnames = self.varnames, selection = self.selection,
                         datasetdir = self.datasetdir, ignorecompilefails = self.ignorecompilefails,
                         aliases = self.aliases, friends = friends, addfriends = (addfriends and self.addfriends),
                         ignorefriends = self.ignorefriends, sortfiles = self.sortfiles,
                         zombiewarning = self.zombiewarning, build = self.build)

    def clone(self, ignoreperfile = False, suffix = '', keepfriends = True, **kwargs):
        '''Get a clone of this DataChain. kwargs can be any that're given to the DataChain constructor,
        which will override the current values.'''
        args = self.__getstate__()
        args.update(kwargs)
        args['name'] += suffix
        if ignoreperfile:
            args['ignorefriends'] = self.get_ignorefriends_perfile(args['ignorefriends'], False)
        if keepfriends and suffix:
            friends = set(args.get('friends', []))
            friends.update(self.friends.values())
            args['friends'] = list(friends)
        return DataChain(**args)

    def clone_for_variables(self, variables = [], ignoreperfile = False, suffix = '', **kwargs):
        '''Get a clone of this DataChain keeping only the friends and variable definitions needed
        for the given variables, and the selection if set/given. This is useful for caching the 
        DataChain keeping only the info needed for certain variables.'''
        if not variables:
            variables = self.varnames
        kwargs['selection'] = kwargs.get('selection', self.selection)
        # Expand out all the variables and get any used aliases so these are kept.
        kwargs['variables'] = {}
        usevariables = []
        usedaliases = {}
        for variable in variables:
            if isinstance(variable, str):
                # Named variable we know about.
                if variable in self.variables:
                    variable = self.variables[variable]
                    subvar, _usedaliases = self.get_used_substitutions(variable.formula)
                    usedaliases.update(_usedaliases)
                    kwargs['variables'][variable.name] = variable
                    usevariables.append(subvar)
                # A string formula.
                else:
                    subvar, _usedaliases = self.get_used_substitutions(variable)
                    usedaliases.update(_usedaliases)
                    usevariables.append(subvar)
            # A NamedFormula instance.
            else:
                # Make sure to use this tree's version of the variable in case of different definitions.
                if variable.name in self.variables:
                    variable = variable.copy(formula = self.variables[variable.name].formula)
                subvar, _usedaliases = self.get_used_substitutions(variable.formula)
                kwargs['variables'][variable.name] = variable
                usedaliases.update(_usedaliases)
                usevariables.append(subvar)
        
        if kwargs['selection']:
            subvar, _usedaliases = self.get_used_substitutions(kwargs['selection'])
            usevariables.append(subvar)
            usedaliases.update(_usedaliases)

        # Add all variables that're aliases
        for name, alias in usedaliases.items():
            if name in self.variables:
                kwargs['variables'][name] = self.variables[name]
        # Also add variables that aren't aliases (name is the same as formula)
        for var in usevariables:
            for _var in StringFormula(var).named_variables():
                if _var in self.variables and _var not in kwargs['variables']:
                    kwargs['variables'][_var] = self.variables[_var]

        kwargs['friends'] = [friend.clone_for_variables(variables, selection = kwargs['selection']) 
                             for friend in self.get_used_friends(expand = False, *usevariables).values()]
        kwargs['addfriends'] = False
        kwargs['ignorefriends'] = []
        return self.clone(ignoreperfile = ignoreperfile, suffix = suffix, keepfriends = False, **kwargs)

    clone_for_cache = clone_for_variables

    def __eq__(self, other):
        try:
            return self.__dict__ == other.__dict__
        except AttributeError:
            return False

    def Show(self, n):
        '''Show the contents of entry n, also for friend trees.'''
        super(DataChain, self).Show(n)
        if not self.GetListOfFriends():
            return
        for info in self.GetListOfFriends():
            info.GetTree().Show(n)

    def draw(self, var, varY = None, varZ = None, nbins = None, nbinsY = None, nbinsZ = None,
             name = None, suffix = '', selection = None, extrasel = None, weight = None, opt = ''):
        '''Make a histo of a variable or 2D histo of two variables. 'var' and 'varY' can be 
        the names of known variables or NamedFormula instances. If this dataset has a 
        default selection it's used if one isn't given.'''
        var = self.variables.get_var(var)
        varY = self.variables.get_var(varY)
        varZ = self.variables.get_var(varZ)
        selection = self.get_selection(selection = selection, extrasel = extrasel, weight = weight)
        if varZ:
            h = self.variables.histo3D(var, varY, varZ, name = name, nbins = nbins, nbinsY = nbinsY,
                                       nbinsZ = nbinsZ, suffix = suffix)
            self.Draw('{3} : {2} : {1} >> {0}'.format(h.GetName(), var.name, varY.name, varZ.name), selection, opt)
        if varY:
            h = self.variables.histo2D(var, varY, name = name, nbins = nbins, nbinsY = nbinsY, suffix = suffix)
            self.Draw('{2} : {1} >> {0}'.format(h.GetName(), var.name, varY.name), selection, opt)
        else:
            h = self.variables.histo(var, name = name, nbins = nbins, suffix = suffix)
            self.Draw('{1} >> {0}'.format(h.GetName(), var.name), selection, opt)
        h.SetDirectory(None)
        return h

    def dataset_file_name(self):
        '''Get the name of the file containing the RooDataset.'''
        return os.path.join(self.datasetdir, self.name + '_Dataset.root')

    def get_friend(self, name):
        '''Get a friend with the given name, automatically prefixing with this tree's name if necessary.'''
        if name in self.friends:
            return self.friends[name]
        if not name.startswith(self.name):
            name = self.name + '_' + name
            if name in self.friends:
                return self.friends[name]
        return None

    def remove_friend(self, friend):
        '''Remove a friend from the list of friends either by name or instance.'''
        if isinstance(friend, str):
            friend = self.get_friend(friend)
            if not friend:
                return
        del self.friends[friend.name]
        friendlist = self.GetListOfFriends()
        friendelm = friendlist.FindObject(friend.GetName())
        friendlist.Remove(friendelm)
        return friend

    def add_friend_tree(self, friendname, adderkwargs, treename = None, perfile = False,
                        makedir = True, zfill = 4):
        '''Add a friend tree to the given dataset.
        friendname = name of the friend dataset
        adderkwargs = list or dict of dicts to be passed as arguments to TreeBranchAdder instances (excluding
          the tree argument)
        treename = name of the friend TTree (default friendname + 'Tree')
        makedir & zfill are passed to frield_file_name.'''
        # Remove the friend if it's currently in the friends list.
        self.remove_friend(friendname)

        if None == treename:
            treename = friendname + 'Tree'
        fout = ROOT.TFile.Open(self.friend_file_name(friendname, treename,
                                                     makedir = makedir, zfill = zfill), 'recreate')
        treeout = ROOT.TTree(treename, treename)
        if isinstance(adderkwargs, dict):
            adders = [TreeBranchAdder(treeout, name = name, **kwargs) for name, kwargs in adderkwargs.items()]
        else:
            adders = [TreeBranchAdder(treeout, **kwargs) for kwargs in adderkwargs]
        for i in tree_loop(self):
            for adder in adders:
                adder.set_value()
            treeout.Fill()
        treeout.Write()
        fout.Close()
        return True

    def selected_file_name(self, makedir = False) :
        '''Get the name of the file containing the TTree of range and selection
        variables created when making the RooDataSet.'''
        return self.friend_file_name('SelectedTree', 'SelectedTree',
                                     makedir = makedir)

    def check_consistency(self):
        '''Check that all files exist, are unique, contain the required TTree, and all the TTrees have 
        the same branches.'''
        success = True

        print('Check dataset', self.name, 'for consistency')
        # Check files are unique
        filesset = set(self.files)
        if len(self.files) != len(filesset) :
            print('Some files are duplicated')
            success = False
            for f in filesset :
                fcount = info['files'].count(f)
                if fcount != 1 :
                    print('File', f, 'appears', fcount, 'times')

        branchnames = []
        for f in self.files :
            tf = ROOT.TFile.Open(f)
            # Check file can be opened.
            if not tf :
                print('File', f, "can't be opened!")
                success = False
                continue
            if tf.IsZombie() :
                print('File', f, "can't be opened!")
                success = False
                continue
            # Check it contains the TTree.
            tree = tf.Get(self.tree)
            if not tree :
                print('File', f, "doesn't contain a TTree named", repr(self.tree))
                success = False
                tf.Close()
                continue
            # Check it has the same branches as the other TTrees.
            if not branchnames :
                branchnames = set(br.GetName() for br in tree.GetListOfBranches())
            thesenames = set(br.GetName() for br in tree.GetListOfBranches())
            if branchnames != thesenames :
                print('Branches in file', f, "don't match the first TTree:")
                print('Branches in this TTree not in the first TTree:', thesenames.difference(branchnames))
                print('Branches in the first TTree not in this TTree:', branchnames.difference(thesenames))
                success = False
            tf.Close()
        for friend in self.friends.values():
            if friend.GetEntries() != self.GetEntries():
                success = False
                print('Friend', friend.name, 'has the wrong number of entries:', friend.GetEntries(),
                      'should be', self.GetEntries())
        for friend in self.friends.values():
            friendsuccess = friend.check_consistency()
            success = friendsuccess and success
        return success

    def parallel_filter(self, outputdir, outputname, selection = None,
                        nthreads = multiprocessing.cpu_count(), zfill = None, overwrite = True,
                        ignorefriends = [], noutputfiles = None):
        '''Filter a dataset with the given selection and save output to the outputdir/outputname/.'''
        outputdir = os.path.join(outputdir, outputname)
        if not os.path.exists(outputdir):
            os.makedirs(outputdir)
        if None == selection:
            selection = self.selection

        # Do each file individually in parallel.
        pool = Pool(processes = nthreads)
        nfiles = self.nfiles()
        if None == zfill:
            zfill = len(str(nfiles))
        procs = []
        if None == noutputfiles:
            noutputfiles = nfiles
        if noutputfiles != 1:
            ignorefriends = self.get_ignorefriends_perfile(ignorefriends)
        nper = int(nfiles/noutputfiles)
        ranges =[[i*nper, (i+1)*nper] for i in xrange(noutputfiles)]
        ranges[-1][-1] = nfiles
        kwargslist = []
        for ifile, iend in ranges:
            kwargs = dict(tree = self, selection = selection,
                          outputdir = outputdir, outputname = outputname, 
                          nthreads = nthreads, zfill = zfill, ifile = ifile, iend = iend,
                          overwrite = overwrite, ignorefriends = ignorefriends)
            kwargslist.append(kwargs)

        if True:#len(kwargslist) == 1:
            for kwargs in kwargslist:
                apply(_parallel_filter, (), kwargs)
            return True

        for kwargs in kwargslist:
            proc = pool.apply_async(_parallel_filter, 
                                    kwds = kwargs)
            procs.append(proc)
        success = True
        for proc in procs:
            proc.wait()
        for proc in procs:
            procsuccess = proc.successful()
            success = success and procsuccess
            if not procsuccess:
                proc.get()
        return success

    def filter(self, outputdir, outputname, selection = None, overwrite = True, ignorefriends = []):
        '''Filter a dataset with the given selection and save output to the outputdir/outputname/.'''
        return self.parallel_filter(outputdir, outputname, selection, nthreads = 1, noutputfiles = 1,
                                    overwrite = overwrite, ignorefriends = ignorefriends)

    def __getstate__(self):
        '''Get state for pickling.'''
        state = {attr : getattr(self, attr) for attr in self._ctorargs}
        state['friends'] = self.initfriends
        return state

    def __setstate__(self, state):
        '''Set state for unpickling.'''
        self.__init__(**state)

    def __reduce__(self):
        '''Reduce method for pickling.'''
        return (DataChain, tuple(getattr(self, ('initfriends' if attr == 'friends' else attr))\
                                 for attr in self._ctorargs))

    def __reduce_ex__(self, i):
        '''Reduce method for pickling.'''
        return self.__reduce__()

    def nfiles(self):
        return len(self.files)

    def dataset_name(self):
        return self.name + '_Dataset'

    def _make_dataset(self):
        '''Make the RooDataset.'''
        selectedtreefile = self.selected_file_name(True)
        return make_roodataset(self.dataset_name(), self.dataset_name(), self, 
                               ignorecompilefails = self.ignorecompilefails,
                               selection = self.selection, selectedtreefile = selectedtreefile,
                               selectedtreename = 'SelectedTree',
                               **dict((var, self.variables[var]) for var in self.varnames))

    def dataset_cache(self, update = False, suffix = '', debug = False, **kwargs):
        '''Get the DataCache for the RooDataset.'''
        kwargs['ignorefriends'] = list(kwargs.get('ignorefriends', [])) + ['SelectedTree']
        tree = self.clone_for_variables(suffix = suffix, **kwargs)
        dsname = tree.dataset_name()
        cache = DataCache(dsname, tree.dataset_file_name(), [dsname],
                          lambda tree : {dsname : tree._make_dataset()}, args = (tree,),
                          debug = debug)
        return cache

    def get_dataset(self, update = False, suffix = '', **kwargs):
        '''Get the RooDataset.'''
        cache = self.dataset_cache(update, suffix, **kwargs)
        dsname = cache.args[0].dataset_name()
        return getattr(cache, dsname)

    def GetListOfAliases(self):
        '''Override GetListOfAliases and set ROOT.kMustCleanup = False on the list (otherwise python
        tries to delete it).'''
        aliases = super(DataChain, self).GetListOfAliases()
        if aliases:
            aliases.SetBit(ROOT.kMustCleanup, False)
        return aliases

    def get_aliases(self):
        '''Get aliases, including those of friends, as a dict.'''
        aliases = {}
        for tree in [self] + self.friends.values():
            aliaslist = tree.GetListOfAliases()
            if not aliaslist:
                continue
            for v in aliaslist:
                aliases[v.GetName()] = v.GetTitle()
        return aliases

    def expand_formula(self, formula):
        '''Get the fully expanded formula, substituting out any aliases.'''
        aliases = self.get_aliases()
        return str(StringFormula(formula).substitute_variables(**aliases))

    def get_used_substitutions(self, formula):
        '''Get the fully expanded formula, substituting out any aliases. Returns the new formula and
        used aliases.'''
        aliases = self.get_aliases()
        newform, used = StringFormula(formula).get_used_substitutions(**aliases)
        return str(newform), used

    def get_used_friends(self, variable, *variables, **kwargs):
        '''Get the friend trees used in the variable formula. Expands out the variables
        unless expand = False is given.'''
        if variables:
            friends = self.get_used_friends(variable)
            for var in variables:
                friends.update(self.get_used_friends(var))
            return friends
        if kwargs.get('expand', True):
            variable = StringFormula(self.expand_formula(variable))
        else:
            variable = StringFormula(variable)
        branches = variable.named_variables()
        friends = {}
        for name, friend in self.friends.items():
            if any(br in friend.GetListOfBranches() for br in branches):
                friends[name] = friend
        return friends

    def cache_directory(self, mkdir = True):
        '''Get the directory for saving caches.'''
        cachedir = os.path.join(self.datasetdir, self.name + '_Cache')
        if mkdir and not os.path.exists(cachedir):
            os.makedirs(cachedir)
        return cachedir

    def cache_file(self, name, mkdir = True):
        '''Get the DataCache file name.'''
        return os.path.join(self.cache_directory(mkdir), name + '.root')

    def get_cache(self, name, names, function, variables = [], selection = None, ignorefriends = [], **kwargs):
        '''Get a DataCache that uses this tree and the given function. The first argument to the function
        should be the tree itself. 'kwargs' is used for the DataCache constructor.'''
        clonekwargs = {}
        if variables:
            clonekwargs['variables'] = variables
        if None != selection:
            clonekwargs['selection'] = selection
        if ignorefriends:
            clonekwargs['ignorefriends'] = ignorefriends
        if clonekwargs:
            tree = self.clone_for_variables(**clonekwargs)
        else:
            tree = self
        args = list(kwargs.get('args', []))
        args.insert(0, tree)
        kwargs['args'] = args
        return DataCache(name, self.cache_file(name), names, function, **kwargs)

    def histo_cache(self, variable, variableY = None, name = None, suffix = '', 
                    selection = None, extrasel = None, **kwargs):
        '''Get a DataCache for plotting a 1D or 2D histo. 'name' is the name of the histo and cache;
        'variable' & 'variableY' can be the names of the variables (which must be defined in the known
        variables) or NamedFormula instances. If 'selection' isn't given, use the default selection. 
        If 'extrasel' is given, append it to the selection. The selection is used as the weight, so 
        can take non-binary values. 'kwargs' is passed to the DataCache constructor (eg, 'update').'''
        if not name:
            name = self.variables.get_var(variable).name
            if variableY:
                name = self.variables.get_var(variableY).name + '_vs_' + name
        if suffix:
            name += suffix
        selection = self.get_selection(selection, extrasel)
        variables = [variable]
        if variableY:
            variables.append(variableY)
        tree = self.clone_for_variables(variables = variables, selection = selection)
        args = (variable, variableY, name)
        def draw_histo(tree, variable, variableY, name):
            return {name : tree.draw(variable, variableY, name = name)}
        return tree.get_cache(name, [name], draw_histo, args = args, **kwargs)

    def get_efficiency(self, passselection, selection = None, extrasel = None):
        '''Get the efficiency of the given selection. If one isn't given, use the default selection.'''
        selection = self.get_selection(selection, extrasel)
        passselection = AND(passselection, selection)
        return float(self.sum_of_weights(passselection))/self.sum_of_weights(selection)

    def plot_efficiency(self, name, passselection, variable, variableY = None, weight = None, drawopt = '', 
                        selection = None, extrasel = None, htype = ROOT.TEfficiency, efflabel = 'Efficiency',
                        variableZ = None):
        '''Plot the efficiency of 'passselection' vs 'variable', optionally 2D vs 'variableY'. If selection
        is None, the default selection is used as the base selection. If extrasel is given, this is added
        to the base selection selection. The efficiency is:
        N(passselection && selection && extrasel)/N(selection && extrasel).'''
        selection = self.get_selection(selection, extrasel)
        passselection = AND(passselection, selection)
        variable = self.variables.get_var(variable)
        variableY = self.variables.get_var(variableY)
        variables = [TreeFormula('xvar', variable.formula, self)]
        if variableZ:
            heff = self.variables.histo3D(variable, variableY, variableZ, name = name, htype = htype)
            variables.append(TreeFormula('yvar', variableY.formula, self))
            variables.append(TreeFormula('zvar', variableZ.formula, self))
        elif variableY:
            heff = self.variables.histo2D(variable, variableY, name = name, htype = htype)
            variables.append(TreeFormula('yvar', variableY.formula, self))
        else:
            heff = self.variables.histo(variable, name = name, htype = htype)
        heff.SetDirectory(None)
        passvar = TreeFormula('passsel', passselection, self)
        weightsel = self.get_selection(selection = selection, weight = weight)
        if weightsel:
            weightvar = self.get_functor('weightvar', weightsel)
            fill = lambda : heff.FillWeighted(bool(passvar()), weightvar(), *[v() for v in variables])
        else:
            fill = lambda : heff.FillWeighted(bool(passvar()), 1., *[v() for v in variables])
        for i in self.loop(selection):
            try:
                fill()
            except:
                print('DataChain.plot_efficiency: exception at entry', i, file = sys.stderr)
                print('Selection:', selection, 'pass selection:', passselection, 'variable:', variable,
                      'variableY:', variableY, 'variableZ:', variableZ)
                raise
        if variableZ:
            painted = ROOT.TH3D(heff.GetPassedHistogram())
            painted.Divide(heff.GetTotalHistogram())
            painted.SetName("efficiency")
            painted.SetDirectory(None)
            variableY.set_y_title(painted)
            variableZ.set_z_title(painted)
            for ix in xrange(1, painted.GetNbinsX()+1) :
                for iy in xrange(1, painted.GetNbinsY()+1) :
                    for iz in xrange(1, painted.GetNbinsZ()+1) :
                        ibin = heff.GetGlobalBin(ix, iy, iz)
                        err = (heff.GetEfficiencyErrorLow(ibin)+heff.GetEfficiencyErrorUp(ibin))/2.
                        painted.SetBinError(ix, iy, iz, err)
        elif variableY:
            painted = heff.CreateHistogram()
            painted.SetDirectory(None)
            variableY.set_y_title(painted)
            painted.GetZaxis().SetTitle(efflabel)
            # Don't know why 2D TEfficiencies don't set errors, maybe cause they're asymmetric.
            for ix in xrange(1, painted.GetNbinsX()+1) :
                for iy in xrange(1, painted.GetNbinsY()+1) :
                    ibin = heff.GetGlobalBin(ix, iy)
                    err = (heff.GetEfficiencyErrorLow(ibin)+heff.GetEfficiencyErrorUp(ibin))/2.
                    painted.SetBinError(ix, iy, err)
        else:
            painted = heff.CreateGraph()
            painted.GetYaxis().SetTitle(efflabel)
        painted.SetName(name + '_painted')
        variable.set_x_title(painted)
        painted.Draw(drawopt)
        return heff, painted

    def efficiency_plot_cache(self, name, passselection, variable, variableY = None, weight = None, drawopt = '', 
                              selection = None, extrasel = None, htype = ROOT.TEfficiency, efflabel = 'Efficiency',
                              variableZ = None, **kwargs):
        '''Make a cache for an efficiency plot made using plot_efficency. 'kwargs' is passed to get_cache.'''
        selection = self.get_selection(selection, extrasel)
        variables = [variable, passselection]
        if variableY:
            variables.append(variableY)
        if variableZ:
            variables.append(variableZ)
        tree = self.clone_for_variables(variables = variables, selection = selection)
        def plot_eff(tree, **kwargs):
            heff, hpainted = tree.plot_efficiency(**kwargs)
            return {kwargs['name'] : heff, kwargs['name'] + '_painted' : hpainted}
        plotkwargs = dict(name = name, passselection = passselection, variable = variable,
                          weight = weight, drawopt = drawopt, htype = htype, efflabel = efflabel)
        if variableY:
            plotkwargs['variableY'] = variableY
        if variableZ:
            plotkwargs['variableZ'] = variableZ
        return tree.get_cache(name, [name, name + '_painted'], plot_eff,
                              kwargs = plotkwargs, **kwargs)
            
    def get_selection(self, selection = None, extrasel = None, weight = None):
        '''Get the selection for this TTree. If no selection is given, the default is used. If 'extrasel'
        is given, it's appended to the selection.'''
        if None == selection:
            selection = self.selection
        if extrasel:
            selection = AND(selection, extrasel)
        if weight:
            selection = product(selection, weight)
        return selection

    def loop(self, selection = None, extrasel = None):
        '''Loop over entries in the TTree passing the given selection. If none is given, the default selection
        is used.'''
        selection = self.get_selection(selection, extrasel)
        return tree_loop(self, selection)

    def __iter__(self):
        return self.loop()

    def compare(self, other):
        '''Compare with another DataChain and print differences.'''
        for k, v in self.__dict__.items():
            vo = other[k]
            if vo != v:
                print('self.{0}.{1} = {2!r}, other.{3}.{1} = {4!r}'.format(self.name, k, v, other.name, vo))

    def get_functor(self, name, formula = None):
        '''Get a TreeFormula instance with the given name and formula.'''
        if not formula:
            var = self.variables.get_var(name)
            try:
                formula = var.name
            except AttributeError:
                formula = name
        return TreeFormula(name, formula, self)

    def mean(self, formula, weight = None, selection = None, extrasel = None):
        '''Get the mean of the given formula.'''
        return tree_mean(self, formula, self.get_selection(selection, extrasel), weight)

    def formula_iter(self, formula, selection = None, extrasel = None):
        '''Iterate over the formula values.'''
        return tree_iter(self, formula, self.get_selection(selection, extrasel))

    def selection_functor(self):
        '''Get the functor for the selection.'''
        if self.selection:
            return self.get_functor('selection', self.selection)
        return lambda : 1.

    def get_functor_list(self, variables):
        '''Get a TreeFormulaList for the given variables.'''
        _vars = []
        for var in variables:
            var = self.variables.get_var(var)
            try:
                _vars.append(var.name)
            except AttributeError:
                _vars.append(var)
        return TreeFormulaList(self, *_vars)

    def add_weight(self, weight):
        '''Append a weight to the selection.'''
        self.selection = self.get_selection(weight = weight)
        return self.selection
        
    def sum_of_weights(self, selection = None, extrasel = None, weight = None):
        '''Get the sum of weights (using the selection).'''
        selection = self.get_selection(selection = selection, extrasel = extrasel, weight = weight)
        if not selection:
            return self.GetEntries()
        return sum(self.formula_iter(selection, selection = selection))

class DataLibrary(object) :
    '''Contains info on datasets and functions to retrieve them.'''

    class DataGetter(object) :
        '''Simple wrapper for dynamic construction of callables to retrieve datasets.'''
        def __init__(self, method, *args) :
            self.method = method
            self.args = args
        
        def __call__(self) :
            return self.method(*self.args)

    def __init__(self, datapaths, variables, ignorecompilefails = False, selection = '', varnames = (),
                 aliases = {}) :
        self.datapaths = {}
        self.variables = NamedFormulae(variables)
        self.varnames = varnames
        self.selection = selection
        self.ignorecompilefails = ignorecompilefails
        self.aliases = aliases
        self.make_getters(datapaths)

    def __getstate__(self):
        '''Get state for pickling.'''
        return {attr : getattr(self, attr) for attr in ('datapaths', 'variables', 'ignorecompilefails',
                                                        'selection', 'varnames', 'aliases')}

    def __setstate__(self, state):
        '''Set state for unpickling.'''
        self.__init__(**state)

    def datasets(self) :
        '''Get the sorted list of dataset names.'''
        return sorted(self.datapaths.keys())

    def get_data_info(self, name) :
        '''Get the info dict on the dataset of the given name without any extra actions.'''
        try :
            info = self.datapaths[name]
        except KeyError :
            raise ValueError('DataLibrary.get_data_info: Unknown data type: ' + repr(name))
        if not isinstance(info, dict) :
            info = {'tree' : info[0], 'files' : info[1:]}
        else:
            info = dict(info)
        for attr in 'variables', 'varnames', 'selection', 'aliases', 'ignorecompilefails':
            if not attr in info:
                info[attr] = getattr(self, attr)
        return info

    def get_ignorefriends_perfile(self, name, ignorefriends = [], warning = True):
        '''Get the names of friend trees that should be ignored for perfile operations.'''
        return self.get_data(name).get_ignorefriends_perfile(ignorefriends, warning)

    def get_data(self, name, ifile = None, iend = None, addfriends = True, ignorefriends = [], build = True) :
        '''Get the dataset of the given name. Optionally for one (ifile) or a range (ifile:iend) of files.
        If addfriends = False, friend trees aren't added.'''
        info = self.get_data_info(name)
        tree = DataChain(name, addfriends = addfriends, ignorefriends = ignorefriends, 
                         build = build, **info)
        if None != ifile:
            tree = tree.get_subset(ifile, iend)
        return tree

    def get_data_frame(self, name, *args, **kwargs):
        '''Get a RDataFrame for the given dataset. Can take any of the arguments to DataLibrary.get_data.'''
        tree = self.get_data(name, *args, **kwargs)
        df = ROOT.RDataFrame(tree)
        # Keep a reference to the TChain in python so it's cleaned up.
        df.tree = tree
        return df

    def dataset_dir(self, dataname):
        '''Get the directory where RooDataSets etc will be saved for this dataset.'''
        return self.get_data(dataname, build = False).datasetdir

    def dataset_file_name(self, dataname) :
        '''Get the name of the file containing the RooDataset corresponding to the given
        dataset name.'''
        return self.get_data(dataname, build = False).dataset_file_name()

    def friends_directory(self, dataname) :
        '''Get the directory containing friends of this dataset that will be automatically loaded.'''
        return self.get_data(dataname, build = False).friends_directory()

    def friend_file_name(self, dataname, friendname, treename, number = None, makedir = False, zfill = 4) :
        '''Get the name of a file that will be automatically added as a friend to the given dataset,
        optionally with a number. 'treename' is the name of the TTree it's expected to contain.
        If makedir = True then the directory to hold the file is created.'''
        return self.get_data(dataname, build = False).friend_file_name(friendname, treename, number, makedir, zfill)

    def add_friend_tree(self, dataname, friendname, adderkwargs, 
                        tree = None, treename = None, perfile = False, makedir = True, zfill = 4):
        '''Add a friend tree to the given dataset.
        friendname = name of the friend dataset
        adderkwargs = list of dicts to be passed as arguments to TreeBranchAdder instances (excluding
          the tree argument)
        treename = name of the friend TTree (default friendname + 'Tree')
        makedir & zfill are passed to frield_file_name.'''
        if None == tree:
            tree = self.get_data(dataname)
        tree.add_friend_tree(friendname, adderkwargs, treename, perfile, makedir, zfill)

    def selected_file_name(self, dataname, makedir = False) :
        '''Get the name of the file containing the TTree of range and selection
        variables created when making the RooDataSet.'''
        return self.get_data(dataname, build = False).selected_file_name(makedir = makedir)

    def get_dataset(self, dataname, varnames = None, update = False, suffix = '', selection = None) :
        '''Get the RooDataSet of the given name. It's created/updated on demand. varnames is the 
        set of variables to be included in the RooDataSet. They must correspond to those defined 
        in the variables module. If the list of varnames changes or if update = True the 
        RooDataSet will be recreated.'''
        kwargs = dict(update = update, suffix = suffix)
        if varnames:
            kwargs['varnames'] = varnames
        if None != selection:
            kwargs['selection'] = selection
        return self.get_data(dataname).get_dataset(**kwargs)

    def add_merged_datasets(self, mergedsub, name1, name2) :
        '''Merge datasets containing name1 or name2 in their name into a new dataset
        of files from both datasets.'''

        # Make merged datasets for both polarities.
        mergeddata = {}
        for name, data in self.datapaths.items() :
            if not (name1 in name or name2 in name) or not 'files' in data :
                continue
            mergedname = name.replace(name1, mergedsub).replace(name2, mergedsub)
            if mergedname in self.datapaths or mergedname in mergeddata :
                continue
            merged = deepcopy(data)
            othername = name.replace(name1, name2) if name1 in name else name.replace(name2, name1)
            if not othername in self.datapaths :
                continue
            merged['files'] += self.datapaths[othername]['files']
            mergeddata[mergedname] = merged
        self.make_getters(mergeddata)

    def get_matching_datasets(self, name, *names):
        '''Get the names of all datasets that contain matches to any of the given regex names. Note that
        you can specify that the regex matches at the start/end of the string by prefixing with ^ or
        suffixing with $ so you can force it to match the entire string.'''
        names = (name,) + names
        datasets = list(filter(lambda dataset: any(re.search(name, dataset) for name in names), self.datasets()))
        return datasets
        
    def get_merged_data(self, name, *names):
        '''Get a TChain that's the combination of all datasets matching the given regex names.'''
        # Annoyingly, TChains don't behave properly when Adding other TChains that have friends,
        # so we have to merge the TChains without friends, merge the friend TChains, and then
        # add them as friends.
        datasetnames = self.get_matching_datasets(name, *names)
        datasets = [self.get_data(dataset) for dataset in datasetnames]
        mergeddata = self.get_data(datasetnames[0], addfriends = False)
        mergeddata.GetEntries()
        mergeddata.mergeddatasets = []
        friends = {friend.name[len(mergeddata.name)+1:] : friend for friend in datasets[0].friends.values()}
        for friend in friends.values():
            friend.GetEntries()
            friend.mergeddatasets = []
        for dataset in datasets[1:]:
            mergeddata.name += '_' + dataset.name
            ds = self.get_data(dataset.name, addfriends = False)
            mergeddata.Add(ds)
            mergeddata.mergeddatasets.append(ds)
            for friend in dataset.friends.values():
                _name = friend.name[len(ds.name)+1:]
                friends[_name].Add(friend)
                friends[_name].mergeddatasets.append(friend)
        for friend in friends.values():
            mergeddata.AddFriend(friend)
        return mergeddata

    def get_merged_dataset(self, name, *names, **kwargs):
        '''Get the total RooDataSet for all datasets matching the given regex names. 'kwargs' is passed to get_dataset,
        and can contain any of the arguments it expects.'''
        datasets = self.get_matching_datasets(name, *names)
        data = self.get_dataset(datasets[0], **kwargs)
        for dataset in datasets[1:]:
            data.append(self.get_dataset(dataset, **kwargs))
        return data

    def get_dataset_update_time(self, name):
        '''Get the time that the RooDataset was last updated.'''
        fname = self.dataset_file_name(name)
        if not os.path.exists(fname):
            return
        return datetime.datetime.fromtimestamp(os.path.getmtime(fname))

    def check_dataset(self, name) :
        '''Check that all files exist, are unique, contain the required TTree, and all the TTrees have 
        the same branches.'''
        return self.get_data(name).check_consistency()

    def check_all_datasets(self) :
        '''Check all datasets for integrity. Returns a list of OK datasets, and a list of
        datasets with problems.'''
        successful = []
        failed = []
        for dataset in self.datasets() :
            print('Check', dataset)
            if not self.check_dataset(dataset) :
                print('Failed!')
                failed.append(dataset)
            else :
                print('OK')
                successful.append(dataset)
            print
        return successful, failed

    def make_getters(self, datapaths) :
        '''Define getter methods for every TTree dataset and corresponding RooDataSet.'''
        self.datapaths.update(datapaths)
        for name in datapaths :
            setattr(self, name, DataLibrary.DataGetter(self.get_data, name))
            setattr(self, name + '_Dataset', DataLibrary.DataGetter(self.get_dataset, name))

    def parallel_filter_data(self, dataset, selection, outputdir, outputname,
                             nthreads = multiprocessing.cpu_count(), zfill = None, overwrite = True,
                             ignorefriends = [], noutputfiles = None):
        '''Filter a dataset with the given selection and save output to the outputdir/outputname/.'''
        data = self.get_data(dataset)
        data.parallel_filter(outputdir = outputdir, outputname = outputname, selection = selection,
                             nthreads = nthreads, zfill = zfill, overwrite = overwrite,
                             ignorefriends = ignorefriends, noutputfiles = noutputfiles)

class BinnedFitData(object) :
    '''Bin a RooDataSet in one or two variables and make RooDataHists of another variable in those bins.'''

    def __init__(self, name, outputdir, workspace, roodata, variable, binvariable, bins, 
                 binvariable2 = None, bins2 = None, nbinsx = 100, xmin = None, xmax = None,
                 get = False, update = False) :
        '''name: name of the file to save to, and the RooDataHist
        outputdir: directory to save to
        workspace: the AnalysisUtils.workspace.Workspace instance
        roodata: the RooDataSet to extract the histos from
        variable: the variable to make the RooDataHists for
        binvariable: the variable to bin in
        bins: the list of bin edges for the bin variable
        binvariable2: optional second binning variable
        bins2: optional bins for second binning variable
        nbinsx: the number of bins for 'variable'
        xmin: the minimum value for 'variable'
        xmax: the maxmimum value for 'variable'
        get: whether to retrieve or build the datasets on initialisation
        update: whether to rebuild the datasets.'''

        self.name = name
        if not os.path.exists(outputdir) :
            os.makedirs(outputdir)
        self.outputfname = os.path.join(outputdir, name + '.root')
        self.workspace = workspace
        self.roodata = roodata
        self.variable = variable
        self.nbinsx = nbinsx
        self.xmin = xmin if None != xmin else variable.getMin()
        self.xmax = xmax if None != xmax else variable.getMax()
        self.binvariable = binvariable
        self.bins = bins
        self.binvariable2 = binvariable2
        self.bins2 = bins2
        self.selections = {}
        self.catvals = {}
        if not binvariable2 :
            zlen = len(str(len(self.bins)-1))
            for ibin, (binmin, binmax) in enumerate(zip(self.bins[:-1], self.bins[1:])) :
                binname = name + '_bin_' + str(ibin).zfill(zlen)
                self.selections[binname] = {binvariable.GetName() : (binmin, binmax)}
                self.catvals[binname] = name + '_bin' + str(ibin).zfill(zlen)
        else :
            nbins = len(self.bins)-1
            nbins2 = len(self.bins2)-1
            ncats = nbins * nbins2 - 1
            zlencat = len(str(ncats))
            zlen = len(str(nbins))
            zlen2 = len(str(nbins2))
            for ibin, (binmin, binmax) in enumerate(zip(self.bins[:-1], self.bins[1:])) :
                for ibin2, (binmin2, binmax2) in enumerate(zip(self.bins2[:-1], self.bins2[1:])) :
                    binname = name + '_bin_{0}_{1}'.format(str(ibin).zfill(zlen), str(ibin2).zfill(zlen2))
                    self.selections[binname] = {binvariable.GetName() : (binmin, binmax),
                                                binvariable2.GetName() : (binmin2, binmax2)}
                    self.catvals[binname] = name + '_bin' + str(ibin * nbins2 + ibin2).zfill(zlencat)
        self.binvar = None
        self.datasets = {}
        self.meanvals = {}
        self.datahist = None

        #print(self.selections)

        if get :
            self.get(update)

    def build(self) :
        '''Build the RooDataHists and save them to the output file.'''
        fout = ROOT.TFile.Open(self.outputfname, 'recreate')
        
        self.binvar = self.workspace.roovar(self.name + '_bin', xmin = 0, xmax = len(self.selections)-1,
                                            discrete = True)
        self.binvar.Write()

        histmap = cppyy.makeClass('std::map<std::string, RooDataHist*>')()
        Histpair = cppyy.makeClass('pair<const string,RooDataHist*>')

        for binname, selection in self.selections.items() :
            # Make the dataset for the bin.
            catval = self.catvals[binname]
            datahist = make_roodatahist(binname, self.roodata, self.variable, selection = selection,
                                        nbins = self.nbinsx, xmin = self.xmin, xmax = self.xmax)
            datahist.Write()
            self.datasets[binname] = datahist
            histmap.insert(Histpair(catval, datahist))

            # Calculate the mean values of the bin variables for the bin.
            meanvals = {name : 0. for name in selection}
            n = 0
            for i in xrange(self.roodata.numEntries()) :
                args = self.roodata.get(i)
                if not all(cut[0] <= args[name].getVal() < cut[1] for name, cut in selection.items()) :
                    continue
                weight = self.roodata.weight()
                for name in selection :
                    meanvals[name] += args[name].getVal() * weight
                n += weight
            if n > 0 :
                for name in selection :
                    meanvals[name] /= n
            self.meanvals[binname] = meanvals
        self.datahist = ROOT.RooDataHist(self.name, self.name, ROOT.RooArgList(self.variable),
                                         self.binvar, histmap)
        self.datahist.Write()
        ROOT.TNamed(self.name + '_meanvals', repr(self.meanvals)).Write()
        fout.Close()

    def retrieve(self) :
        '''Retrieve the RooDataHists from the output file.'''
        if not is_tfile_ok(self.outputfname) :
            return False
        fout = ROOT.TFile.Open(self.outputfname)
        self.datahist = fout.Get(self.name)
        self.datasets = {binname : fout.Get(binname) for binname in self.selections}
        self.meanvals = fout.Get(self.name + '_meanvals')
        self.binvar = fout.Get(self.name + '_bin')
        fout.Close()
        if not all(list(self.datasets.values()) + [self.datahist, self.meanvals, self.binvar]) :
            self.datahist = None
            self.datasets = {}
            self.meanvals = {}
            self.binvar = None
            return False
        self.meanvals = eval(self.meanvals.GetTitle())
        return True

    def get(self, update = False) :
        '''Try to retrieve, if that fails, call build.'''
        if update or not self.retrieve() :
            self.build()

    def categories(self):
        '''Get the sorted list of categories.'''
        return sorted(self.catvals.values())

    def bin_names(self):
        '''Get the sorted list of bin names.'''
        return sorted(self.catvals.keys())

    def make_roosimultaneous(self, pdfs, pref = '') :
        '''Make a RooSimultaneous in the bin category variable and add the given PDFs. 'pdfs' should be a dict
        with keys the category names (as given by categories() or bin_names()) and values the PDFs for each category value.'''

        simul = ROOT.RooSimultaneous(pref + self.name + '_pdf', '', self.binvar)
        for catname, pdf in pdfs.items() :
            if catname in self.catvals:
                catname = self.catvals[catname]
            if simul.addPdf(pdf, catname) :
                raise ValueError('Something went wrong adding PDF {0} for category {1}'.format(pdf.GetName(),
                                                                                               catname))
        return simul
