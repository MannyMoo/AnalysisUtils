'''Functions to access all the relevant datasets for the analysis, both TTrees and RooDataSets.'''

import os, ROOT, pprint, cppyy, glob, re
from AnalysisUtils.makeroodataset import make_roodataset, make_roodatahist
from AnalysisUtils.treeutils import make_chain, set_prefix_aliases, check_formula_compiles, is_tfile_ok
from array import array
from copy import deepcopy

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
        self.datapaths = {}
        self.variables = variables
        self.varnames = varnames
        self.selection = selection
        self.ignorecompilefails = ignorecompilefails
        self.make_getters(datapaths)

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

    def datasets(self) :
        '''Get the sorted list of dataset names.'''
        return sorted(self.datapaths.keys())

    def _get_data_info(self, name) :
        '''Get the info dict on the dataset of the given name without any extra actions.'''
        try :
            info = self.datapaths[name]
            if not isinstance(info, dict) :
                info = {'tree' : info[0], 'files' : info[1:]}
            return info
        except KeyError :
            raise ValueError('Unknown data type: ' + repr(name))

    def add_friends(self, name) :
        '''Add friends of the given dataset from the files under its friends directory.'''
        info = self._get_data_info(name)
        friendsdir = self.friends_directory(name)
        if not os.path.exists(friendsdir) :
            return
        friends = info.get('friends', [])
        for friendname in os.listdir(friendsdir) :
            files = sorted(glob.glob(os.path.join(friendsdir, friendname, '*.root')))
            if not files :
                continue
            fname = os.path.split(files[0])[1]
            # Take the name of the file as the name of the TTree
            treename = fname[:-len('.root')]
            # Check if the file ends with _[0-9]+, in which case remove it.
            if re.search('_[0-9]+\.root', fname) :
                treename = '_'.join(treename.split('_')[:-1])
            friendname = name + '_' + friendname
            if not friendname in self.datapaths :
                self.make_getters({friendname : {'files' : files,
                                                 'tree' : treename}})
            if not friendname in friends :
                friends.append(friendname)
        if friends :
            info['friends'] = friends
            self.datapaths[name] = info

    def get_data_info(self, name) :
        '''Get the info dict on the dataset of the given name.'''
        self.add_friends(name)
        info = self._get_data_info(name)
        return info

    def get_data(self, name) :
        '''Get the dataset of the given name.'''
        info = self.get_data_info(name)
        t = make_chain(info['tree'], *info['files'])
        aliases = info.get('aliases', {})
        set_prefix_aliases(t, aliases)
        if 'variables' in info :
            t.variables = dict(self.variables)
            t.variables.update(info['variables'])
        if 'selection' in info :
            t.selection = info['selection']
        for varname, varinfo in self._variables(t).items() :
            t.SetAlias(varname, varinfo['formula'])
        if 'friends' in info :
            for friend in info['friends'] :
                t.AddFriend(self.get_data(friend))
        return t

    def dataset_file_name(self, dataname) :
        '''Get the name of the file containing the RooDataset corresponding to the given
        dataset name.'''
        info = self._get_data_info(dataname)
        if 'datasetdir' in info :
            dirname = info['datasetdir']
        else :
            dirname = os.path.dirname(info['files'][0])
        return os.path.join(dirname, dataname + '_Dataset.root')

    def friends_directory(self, dataname) :
        '''Get the directory containing friends of this dataset that will be automatically loaded.'''
        return self.dataset_file_name(dataname)[:-len('_Dataset.root')] + '_Friends'

    def friend_file_name(self, dataname, friendname, treename, number = None, makedir = False) :
        '''Get the name of a file that will be automatically added as a friend to the given dataset,
        optionally with a number. 'treename' is the name of the TTree it's expected to contain.
        If makedir = True then the directory to hold the file is created.'''
        if None != number :
            fname = treename + '_' + str(number) + '.root'
        else :
            fname = treename + '.root'
        dirname = os.path.join(self.friends_directory(dataname), friendname)
        if makedir and not os.path.exists(dirname) :
            os.makedirs(dirname)
        return os.path.join(dirname, fname)

    def selected_file_name(self, dataname) :
        '''Get the name of the file containing the TTree of range and selection
        variables created when making the RooDataSet.'''
        return os.path.join(self.friends_directory(dataname), 'SelectedTree', 'SelectedTree.root')

    def retrieve_dataset(self, dataname, varnames) :
        '''Retrieve a previously saved RooDataSet for the given dataset and check that it contains
        variables with the given names. If the file or RooDataSet doesn't exist, or the RooDataSet
        contains different variables, returns None.'''

        tree = self.get_data(dataname)

        fout = ROOT.TFile.Open(self.dataset_file_name(dataname))
        if not fout or fout.IsZombie():
            return
        if self.ignorecompilefails :
            variables = self._variables(tree)
            checkvarnames = filter(lambda name : check_formula_compiles(variables[name]['formula'],
                                                                        tree),
                                   varnames)
        else :
            checkvarnames = varnames
        checkvarnames = set(checkvarnames)
        dataset = fout.Get(dataname)
        datanames = set(dataset.get(0).contentsString().split(','))
        if dataset and checkvarnames == datanames :
            fout.Close()
            return dataset
        print 'Variables for dataset', dataname, 'have changed. Expected', checkvarnames, 'found', datanames, '. RooDataSet will be updated.'
        fout.Close()

    def get_dataset(self, dataname, varnames = None, update = False) :
        '''Get the RooDataSet of the given name. It's created/updated on demand. varnames is the 
        set of variables to be included in the RooDataSet. They must correspond to those defined 
        in the variables module. If the list of varnames changes or if update = True the 
        RooDataSet will be recreated.'''

        if not varnames :
            varnames = self.varnames
        if not update :
            dataset = self.retrieve_dataset(dataname, varnames)
            if dataset:
                return dataset

        print 'Making RooDataSet for', dataname

        tree = self.get_data(dataname)
        variables = self._variables(tree)
        selectedtreefile = self.selected_file_name(dataname)
        selectedtreedir = os.path.dirname(selectedtreefile)
        if not os.path.exists(selectedtreedir) :
            os.makedirs(selectedtreedir)
        dataset = make_roodataset(dataname, dataname, tree,
                                  ignorecompilefails = self.ignorecompilefails,
                                  selection = self._selection(tree),
                                  selectedtreefile = selectedtreefile,
                                  selectedtreename = 'SelectedTree',
                                  **dict((var, variables[var]) for var in varnames))

        fname = self.dataset_file_name(dataname)
        print 'Saving to', fname
        fout = ROOT.TFile.Open(fname, 'recreate')
        dataset.Write()
        fout.Close()
        return dataset

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

    def add_single_file_datasets(self, name) :
        '''Add datasets split by files for the given dataset name.'''
        info = get_data_info(name)
        

    def check_dataset(self, name) :
        '''Check that all files exist, are unique, contain the required TTree, and all the TTrees have 
        the same branches.'''
        info = self.get_data_info(name)
        success = True

        # Check files are unique
        filesset = set(info['files'])
        if len(info['files']) != len(filesset) :
            print 'Some files are duplicated'
            success = False
            for f in filesset :
                fcount = info['files'].count(f)
                if fcount != 1 :
                    print 'File', f, 'appears', fcount, 'times'

        branchnames = []
        for f in info['files'] :
            tf = ROOT.TFile.Open(f)
            # Check file can be opened.
            if not tf :
                print 'File', f, "can't be opened!"
                success = False
                continue
            if tf.IsZombie() :
                print 'File', f, "can't be opened!"
                success = False
                continue
            # Check it contains the TTree.
            tree = tf.Get(info['tree'])
            if not tree :
                print 'File', f, "doesn't contain a TTree named", repr(info['tree'])
                success = False
                tf.Close()
                continue
            # Check it has the same branches as the other TTrees.
            if not branchnames :
                branchnames = set(br.GetName() for br in tree.GetListOfBranches())
            thesenames = set(br.GetName() for br in tree.GetListOfBranches())
            if branchnames != thesenames :
                print 'Branches in file', f, "don't match the first TTree:"
                print 'Branches in this TTree not in the first TTree:', thesenames.difference(branchnames)
                print 'Branches in the first TTree not in this TTree:', branchnames.difference(thesenames)
                success = False
            tf.Close()
        return success

    def check_all_datasets(self) :
        '''Check all datasets for integrity. Returns a list of OK datasets, and a list of
        datasets with problems.'''
        successful = []
        failed = []
        for dataset in self.datasets() :
            print 'Check', dataset
            if not self.check_dataset(dataset) :
                print 'Failed!'
                failed.append(dataset)
            else :
                print 'OK'
                successful.append(dataset)
            print
        return successful, failed

    def make_getters(self, datapaths) :
        '''Define getter methods for every TTree dataset and corresponding RooDataSet.'''
        self.datapaths.update(datapaths)
        for name in datapaths :
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

class BinnedFitData(object) :

    def __init__(self, name, outputdir, workspace, roodata, variable, binvariable, bins, 
                 binvariable2 = None, bins2 = None, nbinsx = 100, xmin = None, xmax = None,
                 get = False, update = False) :
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

        #print self.selections

        if get :
            self.get(update)

    def build(self) :
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
        if update or not self.retrieve() :
            self.build()

    def make_roosimultaneous(self, pdfs, pref = '') :
        simul = ROOT.RooSimultaneous(pref + self.name + '_pdf', '', self.binvar)
        for catname, pdf in pdfs.items() :
            if simul.addPdf(pdf, catname) :
                raise ValueError('Something went wrong adding PDF {0} for category {1}'.format(pdf.GetName(),
                                                                                               catname))
        return simul
