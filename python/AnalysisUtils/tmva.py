import ROOT, os
from ROOT import TMVA
from AnalysisUtils.treeutils import tree_iter, random_string, copy_tree, TreeBranchAdder, TreeFormula, tree_loop, \
    TreeFormulaList
from AnalysisUtils.selection import AND, NOT
from AnalysisUtils.addmva import MVACalc

class TMVAOptions(object) :
    '''Wrapper for options passed to TMVA.'''

    def __init__(self, *args, **kwargs) :
        '''Constructor. Unnamed args are just converted to strings. Named args are converted to
        strings of 'name=val'. All args are joined with ':'.'''
        self.args = args
        self.kwargs = kwargs

    def __str__(self) :
        args = ':'.join(str(arg) for arg in self.args)
        kwargs = ':'.join(str(name) + '=' + str(val) for name, val in self.kwargs.items())
        return ':'.join(filter(None, [args, kwargs]))

    @staticmethod
    def from_string(strval) :
        '''Convert from a string of options.'''
        splitvals = strval.split(':')
        args = []
        kwargs = {}
        for val in splitvals :
            if not '=' in val :
                args.append(val)
                continue
            name, val = val.split('=')
            kwargs[name] = val
        return TMVAOptions(*args, **kwargs)

    def copy(self, *args, **kwargs) :
        '''Return a copy of these options, optionally updating it with the given options.'''
        opts = TMVAOptions(*self.args, **self.kwargs)
        opts.update(*args, **kwargs)
        return opts

    def update(self, *args, **kwargs) :
        '''Update with the given options. 'args' can either be strings or TMVAOptions instances.'''
        for arg in args :
            if isinstance(arg, TMVAOptions) :
                self.update(*arg.args, **arg.kwargs)
            else :
                self.args += (arg,)
        self.kwargs.update(kwargs)

class TMVADataLoader(object) :
    '''Wrapper for TMVA.DataLoader.'''

    def __init__(self, signaltree, backgroundtree, variables, spectators = (),
                 signalweight = '', backgroundweight = '',
                 signalcut = '', backgroundcut = '',
                 signalglobalweight = 1., backgroundglobalweight = 1.,
                 name = 'dataset', splitoptions = None, trainingcut = '',
                 testingcut = '') :
        '''signaltree : the signal TTree.
        backgroundtree : the background TTree.
        variables : list of training variables. These can just be the variable expressions as strings, or
          a list of arguments to be passed to TMVA.DataLoader.AddVariable.
        spectators : same as variables, for spectator variables which are included in the output but not
          used for training.
        signalweight : expression for the signal weight.
        backgroundweight : expression for the background weight.
        signalcut : selection for the signal.
        backgroundcut : selection for the background.
        signalglobalweight : global weight for signal.
        backgroundglobalweight : global weight for the background.
        name : name of the TMVA.DataLoader instance.
        splitoptions : options for TMVA.DataLoader.PrepareTrainingAndTestTree. If None the default is used.
        '''

        if None == splitoptions :
            splitoptions = TMVADataLoader.default_split_options()
        elif isinstance(splitoptions, str) :
            splitoptions = TMVAOptions.from_string(splitoptions)

        if trainingcut and not testingcut :
            testingcut = NOT(trainingcut)
        elif testingcut and not trainingcut :
            trainingcut = NOT(testingcut)

        for attr, val in locals().items() :
            if attr == 'self' :
                continue
            setattr(self, attr, val)

        self.dataloader = self._make_dataloader()

    @staticmethod
    def default_split_options(*args, **kwargs) :
        '''Get the default DataLoader options, optionally updating them with the given args.'''
        opts = TMVAOptions.from_string('nTrain_Signal=0:nTrain_Background=0:SplitMode=Random:NormMode=NumEvents:!V')
        opts.update(*args, **kwargs)
        return opts

    def _make_dataloader(self) :
        '''Make the DataLoader for training.'''

        # Load the data.
        dataloader = TMVA.DataLoader(self.name)

        # Add training variables.
        for var in self.variables :
            if not isinstance(var, (tuple, list)) :
                var = (var,)
            try :
                dataloader.AddVariable(*var)
            except :
                print 'Failed to call dataloader.AddVariable with args', var
                raise 

        # Add spectator variables.
        for var in self.spectators :
            if not isinstance(var, (tuple, list)) :
                var = (var,)
            try :
                dataloader.AddSpectator(*var)
            except :
                print 'Failed to call dataloader.AddSpectator with args', var
                raise 

        # Register trees.
        # If we have explicit cuts for training and testing, we need to copy the TTrees first,
        # applying these cuts.
        if self.trainingcut :
            pwd = ROOT.gROOT.CurrentDirectory()
            self.tmpfile = ROOT.TFile.Open('DataLoader_' + random_string() + '.root', 'recreate')
            usedleaves = self.used_leaves(dataloader)
            for name in 'Signal', 'Background' :
                lname = name.lower()
                namecut = getattr(self, lname + 'cut')
                for ttype, cut in (TMVA.Types.kTraining, self.trainingcut), (TMVA.Types.kTesting, self.testingcut) :
                    cut = AND(*filter(None, [namecut, cut]))
                    tree = getattr(self, lname + 'tree')
                    if tree.GetListOfFriends() :
                        seltree, copyfriends = copy_tree(tree, cut, keepbranches = usedleaves)
                        for fr in copyfriends :
                            fr.Write()
                    else :
                        seltree = copy_tree(tree, cut)
                    seltree.Write()
                    dataloader.AddTree(seltree, name, getattr(self, lname + 'globalweight'),
                                       ROOT.TCut(''), ttype)
                weight = getattr(self, lname + 'weight')
                if weight :
                    dataloader.SetWeightExpression(weight, name)

            dataloader.GetDataSetInfo().SetSplitOptions(str(self.splitoptions))
            pwd.cd()

        else :
            dataloader.AddSignalTree(self.signaltree, self.signalglobalweight)
            dataloader.AddBackgroundTree(self.backgroundtree, self.backgroundglobalweight)

            # Set weight expressions.
            if self.signalweight :
                dataloader.SetSignalWeightExpression(self.signalweight)
            if self.backgroundweight :
                dataloader.SetBackgroundWeightExpression(self.backgroundweight)

            # Prepare the training.
            dataloader.PrepareTrainingAndTestTree(ROOT.TCut(self.signalcut), ROOT.TCut(self.backgroundcut),
                                                  str(self.splitoptions))

        return dataloader

    def get_cut_range_opts(self) :
        '''Get the options for cut ranges, so they stay within the range of the data.'''

        print 'Calculating variable ranges.'
        datasetinfo = self.dataloader.GetDataSetInfo()
        cutrangeopts = TMVAOptions()
        for ivar, varinfo in enumerate(datasetinfo.GetVariableInfos()) :
            varmin = min(min(tree_iter(self.signaltree, str(varinfo.GetExpression()), self.signalcut)), 
                         min(tree_iter(self.backgroundtree, str(varinfo.GetExpression()), self.backgroundcut)))
            varmax = max(max(tree_iter(self.signaltree, str(varinfo.GetExpression()), self.signalcut)), 
                         max(tree_iter(self.backgroundtree, str(varinfo.GetExpression()), self.backgroundcut)))
            print 'Range of', varinfo.GetExpression(), varmin, varmax
            varbuffer = (varmax - varmin)*0.05
            cutrangeopts.update(**{'CutRangeMin[{0}]'.format(ivar) : varmin - varbuffer,
                                   'CutRangeMax[{0}]'.format(ivar) : varmax + varbuffer})
        print 'Cut ranges:'
        print cutrangeopts
        return cutrangeopts

    def used_leaves(self, dataloader = None) :
        '''Get the list of leaves used by the variables and weight expressions (not the cuts).'''
        if not dataloader :
            dataloader = self.dataloader
        datasetinfo = dataloader.GetDataSetInfo()
        forms = [str(varinfo.GetExpression()) for varinfo in datasetinfo.GetVariableInfos()]
        forms += [str(varinfo.GetExpression()) for varinfo in datasetinfo.GetSpectatorInfos()]
        forms += [self.signalweight, self.backgroundweight]
        forms = filter(None, forms)
        return TreeFormulaList(self.signaltree, *forms).used_leaves()

    def __del__(self) :
        if hasattr(self, 'tmpfile') :
            self.tmpfile.Close()
            os.rm(self.tmpfile.GetName())

class TMVAClassifier(object) :
    '''Run TMVA classification algos.'''

    defaultopts = \
        {'BDT': TMVAOptions.from_string('!H:!V:NTrees=850:MinNodeSize=2.5%:MaxDepth=3:BoostType=AdaBoost:AdaBoostBeta=0.5:SeparationType=GiniIndex:nCuts=20'),
         'BDTB': TMVAOptions.from_string('!H:!V:NTrees=400:BoostType=Bagging:SeparationType=GiniIndex:nCuts=20'),
         'BDTD': TMVAOptions.from_string('!H:!V:NTrees=400:MinNodeSize=5%:MaxDepth=3:BoostType=AdaBoost:SeparationType=GiniIndex:nCuts=20:VarTransform=Decorrelate'),
         'BDTG': TMVAOptions.from_string('!H:!V:NTrees=1000:MinNodeSize=1.5%:BoostType=Grad:Shrinkage=0.10:UseBaggedGrad:GradBaggingFraction=0.5:nCuts=20:MaxDepth=2'),
         'BoostedFisher': TMVAOptions.from_string('H:!V:Boost_Num=20:Boost_Transform=log:Boost_Type=AdaBoost:Boost_AdaBoostBeta=0.2'),
         'CFMlpANN': TMVAOptions.from_string('!H:!V:NCycles=2000:HiddenLayers=N+1,N'),
         'Cuts': TMVAOptions.from_string('!H:!V:FitMethod=MC:EffSel:SampleSize=200000:VarProp=FMax'),
         'CutsD': TMVAOptions.from_string('!H:!V:FitMethod=MC:EffSel:SampleSize=200000:VarProp=FMax:VarTransform=Decorrelate'),
         'CutsGA': TMVAOptions.from_string('H:!V:FitMethod=GA:VarProp=FMax:EffSel:Steps=60:Cycles=10:PopSize=1000:SC_steps=10:SC_rate=5:SC_factor=0.95'),
         'CutsPCA': TMVAOptions.from_string('!H:!V:FitMethod=MC:EffSel:SampleSize=200000:VarTransform=PCA:VarProp=FMax'),
         'CutsSA': TMVAOptions.from_string('!H:!V:FitMethod=SA:EffSel:MaxCalls=150000:KernelTemp=IncAdaptive:InitialTemp=1e+6:MinTemp=1e-6:Eps=1e-10:UseDefaultScale:VarProp=FMax'),
         'FDA_GA': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=GA:PopSize=300:Cycles=3:Steps=20:Trim=True:SaveBestGen=1'),
         'FDA_GAMT': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=GA:Converger=MINUIT:ErrorLevel=1:PrintLevel=-1:FitStrategy=0:!UseImprove:!UseMinos:SetBatch:Cycles=1:PopSize=5:Steps=5:Trim'),
         'FDA_MC': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=MC:SampleSize=100000:Sigma=0.1'),
         'FDA_MCMT': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=MC:Converger=MINUIT:ErrorLevel=1:PrintLevel=-1:FitStrategy=0:!UseImprove:!UseMinos:SetBatch:SampleSize=20'),
         'FDA_MT': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=MINUIT:ErrorLevel=1:PrintLevel=-1:FitStrategy=2:UseImprove:UseMinos:SetBatch'),
         'FDA_SA': TMVAOptions.from_string('H:!V:Formula=(0)+(1)*x0+(2)*x1+(3)*x2+(4)*x3:ParRanges=(-1,1)(-10,10);(-10,10);(-10,10);(-10,10):FitMethod=SA:MaxCalls=15000:KernelTemp=IncAdaptive:InitialTemp=1e+6:MinTemp=1e-6:Eps=1e-10:UseDefaultScale'),
         'Fisher': TMVAOptions.from_string('H:!V:Fisher:CreateMVAPdfs:PDFInterpolMVAPdf=Spline2:NbinsMVAPdf=50:NsmoothMVAPdf=10'),
         'FisherG': TMVAOptions.from_string('H:!V:VarTransform=Gauss'),
         'HMatrix': TMVAOptions.from_string('!H:!V'),
         'KNN': TMVAOptions.from_string('H:nkNN=20:ScaleFrac=0.8:SigmaFact=1.0:Kernel=Gaus:UseKernel=F:UseWeight=T:!Trim'),
         'LD': TMVAOptions.from_string('H:!V:VarTransform=None:CreateMVAPdfs:PDFInterpolMVAPdf=Spline2:NbinsMVAPdf=50:NsmoothMVAPdf=10'),
         'Likelihood': TMVAOptions.from_string('H:!V:!TransformOutput:PDFInterpol=Spline2:NSmoothSig[0]=20:NSmoothBkg[0]=20:NSmoothBkg[1]=10:NSmooth=1:NAvEvtPerBin=50'),
         'LikelihoodD': TMVAOptions.from_string('!H:!V:TransformOutput:PDFInterpol=Spline2:NSmoothSig[0]=20:NSmoothBkg[0]=20:NSmooth=5:NAvEvtPerBin=50:VarTransform=Decorrelate'),
         'LikelihoodKDE': TMVAOptions.from_string('!H:!V:!TransformOutput:PDFInterpol=KDE:KDEtype=Gauss:KDEiter=Adaptive:KDEFineFactor=0.3:KDEborder=None:NAvEvtPerBin=50'),
         'LikelihoodMIX': TMVAOptions.from_string('!H:!V:!TransformOutput:PDFInterpolSig[0]=KDE:PDFInterpolBkg[0]=KDE:PDFInterpolSig[1]=KDE:PDFInterpolBkg[1]=KDE:PDFInterpolSig[2]=Spline2:PDFInterpolBkg[2]=Spline2:PDFInterpolSig[3]=Spline2:PDFInterpolBkg[3]=Spline2:KDEtype=Gauss:KDEiter=Nonadaptive:KDEborder=None:NAvEvtPerBin=50'),
         'LikelihoodPCA': TMVAOptions.from_string('!H:!V:!TransformOutput:PDFInterpol=Spline2:NSmoothSig[0]=20:NSmoothBkg[0]=20:NSmooth=5:NAvEvtPerBin=50:VarTransform=PCA'),
         'MLP': TMVAOptions.from_string('H:!V:NeuronType=tanh:VarTransform=N:NCycles=600:HiddenLayers=N+5:TestRate=5:!UseRegulator'),
         'MLPBFGS': TMVAOptions.from_string('H:!V:NeuronType=tanh:VarTransform=N:NCycles=600:HiddenLayers=N+5:TestRate=5:TrainingMethod=BFGS:!UseRegulator'),
         'MLPBNN': TMVAOptions.from_string('H:!V:NeuronType=tanh:VarTransform=N:NCycles=600:HiddenLayers=N+5:TestRate=5:TrainingMethod=BFGS:UseRegulator'),
         'PDEFoam': TMVAOptions.from_string('!H:!V:SigBgSeparate=F:TailCut=0.001:VolFrac=0.0666:nActiveCells=500:nSampl=2000:nBin=5:Nmin=100:Kernel=None:Compress=T'),
         'PDEFoamBoost': TMVAOptions.from_string('!H:!V:Boost_Num=30:Boost_Transform=linear:SigBgSeparate=F:MaxDepth=4:UseYesNoCell=T:DTLogic=MisClassificationError:FillFoamWithOrigWeights=F:TailCut=0:nActiveCells=500:nBin=20:Nmin=400:Kernel=None:Compress=T'),
         'PDERS': TMVAOptions.from_string('!H:!V:NormTree=T:VolumeRangeMode=Adaptive:KernelEstimator=Gauss:GaussSigma=0.3:NEventsMin=400:NEventsMax=600'),
         'PDERSD': TMVAOptions.from_string('!H:!V:VolumeRangeMode=Adaptive:KernelEstimator=Gauss:GaussSigma=0.3:NEventsMin=400:NEventsMax=600:VarTransform=Decorrelate'),
         'PDERSPCA': TMVAOptions.from_string('!H:!V:VolumeRangeMode=Adaptive:KernelEstimator=Gauss:GaussSigma=0.3:NEventsMin=400:NEventsMax=600:VarTransform=PCA'),
         'RuleFit': TMVAOptions.from_string('H:!V:RuleFitModule=RFTMVA:Model=ModRuleLinear:MinImp=0.001:RuleMinDist=0.001:NTrees=20:fEventsMin=0.01:fEventsMax=0.5:GDTau=-1.0:GDTauPrec=0.01:GDStep=0.01:GDNSteps=10000:GDErrScale=1.02'),
         'SVM': TMVAOptions.from_string('Gamma=0.25:Tol=0.001:VarTransform=Norm'),
         'TMlpANN': TMVAOptions.from_string('!H:!V:NCycles=200:HiddenLayers=N+1,N:LearningMethod=BFGS:ValidationFraction=0.3')}
    
    methodtypes = \
        {'BDT': TMVA.Types.kBDT,
         'BDTB': TMVA.Types.kBDT,
         'BDTD': TMVA.Types.kBDT,
         'BDTG': TMVA.Types.kBDT,
         'BoostedFisher': TMVA.Types.kFisher,
         'CFMlpANN': TMVA.Types.kCFMlpANN,
         'Cuts': TMVA.Types.kCuts,
         'CutsD': TMVA.Types.kCuts,
         'CutsGA': TMVA.Types.kCuts,
         'CutsPCA': TMVA.Types.kCuts,
         'CutsSA': TMVA.Types.kCuts,
         'FDA_GA': TMVA.Types.kFDA,
         'FDA_GAMT': TMVA.Types.kFDA,
         'FDA_MC': TMVA.Types.kFDA,
         'FDA_MCMT': TMVA.Types.kFDA,
         'FDA_MT': TMVA.Types.kFDA,
         'FDA_SA': TMVA.Types.kFDA,
         'Fisher': TMVA.Types.kFisher,
         'FisherG': TMVA.Types.kFisher,
         'HMatrix': TMVA.Types.kHMatrix,
         'KNN': TMVA.Types.kKNN,
         'LD': TMVA.Types.kLD,
         'Likelihood': TMVA.Types.kLikelihood,
         'LikelihoodD': TMVA.Types.kLikelihood,
         'LikelihoodKDE': TMVA.Types.kLikelihood,
         'LikelihoodMIX': TMVA.Types.kLikelihood,
         'LikelihoodPCA': TMVA.Types.kLikelihood,
         'MLP': TMVA.Types.kMLP,
         'MLPBFGS': TMVA.Types.kMLP,
         'MLPBNN': TMVA.Types.kMLP,
         'PDEFoam': TMVA.Types.kPDEFoam,
         'PDEFoamBoost': TMVA.Types.kPDEFoam,
         'PDERS': TMVA.Types.kPDERS,
         'PDERSD': TMVA.Types.kPDERS,
         'PDERSPCA': TMVA.Types.kPDERS,
         'RuleFit': TMVA.Types.kRuleFit,
         'SVM': TMVA.Types.kSVM,
         'TMlpANN': TMVA.Types.kTMlpANN}

    def __init__(self, dataloader, methods, weightsdir = '.', outputfile = 'TMVA.root',
                 name = 'TMVAClassification',
                 verbose = False, factoryoptions = None) :
        '''dataloader : the TMVA.DataLoader instance used for input.
        methods : methods to train. Can be a list of method names, in which case the default options
          are used, or a dict of method : options. Here options can be a string or TMVAOptions instance.
        weightsdir : directory in which to save the output.
        outputfile : name of the output file.
        name : name of the TMVA.Factory instance.
        verbose : if the TMVA.Factory is verbose.
        factoryoptions : options for the TMVA.Factory. If None the default is used.
        '''

        if None == factoryoptions :
            factoryoptions = TMVAClassifier.default_factory_options()
        elif isinstance(factoryoptions, str) :
            factoryoptions = TMVAOptions.from_string(factoryoptions)

        for attr, val in locals().items() :
            if attr == 'self' :
                continue
            setattr(self, attr, val)

    @staticmethod
    def default_factory_options(*args, **kwargs) :
        '''Get the default TMVAFactory options, optionally updating them with the given args.'''
        opts = TMVAOptions.from_string('!V:!Silent:Color:!DrawProgressBar:Transformations=I;D;P;G,D:AnalysisType=Classification')
        opts.update(*args, **kwargs)
        return opts

    @staticmethod
    def default_method_options(method, *args, **kwargs) :
        '''Get the default options for the given method, optionally updating them with the given args.'''
        return TMVAOptions.defaultopts[method].copy(*args, **kwargs)

    def get_method_args(self) :
        '''Get the method arguments.'''
        
        # Check method options.
        # If we just have a list of methods, use the default options.
        if not isinstance(self.methods, dict) :
            methods = {method : TMVAClassifier.defaultopts[method].copy() for method in self.methods}
        else :
            methods = dict(self.methods)
        
        # If the args for a method is just a string, use the default type and name.
        for method, args in methods.items() :
            if not isinstance(args, (tuple, list)) :
                args = (TMVAClassifier.methodtypes[method], method, args)
                methods[method] = args
        
        # Convert string options to TMVAOptions.
        for method, args in methods.items() :
            if not isinstance(args[-1], TMVAOptions) :
                methods[method] = args[:-1] + (TMVAOptions.from_string(args[-1]),)

        # If any of the Cuts algos are requested, calcuate the min and max of each training
        # variable and add this to the options, so the algo doesn't try regions that don't
        # have any data.
        if any('Cuts' in method for method in methods) :

            cutrangeopts = self.dataloader.get_cut_range_opts()
            
            for method in methods :
                if not 'Cuts' in method :
                    continue
                methods[method][-1].update(cutrangeopts)

        for method, args in methods.items() :
            methods[method] = args[:-1] + (str(args[-1]),)
        return methods

    def book_methods(self, factory) :
        '''Book the methods in the given factory.'''
        # Book the methods.
        methods = self.get_method_args()
        if isinstance(factory, TMVA.Factory) :
            for method, args in methods.items() :
                print 'Book method', method, 'with options', args[-1]
                factory.BookMethod(self.dataloader.dataloader, *args)        
        else :
            for method, args in methods.items() :
                print 'Book method', method, 'with options', args[-1]
                factory.BookMethod(*args)        
        return methods

    def weights_file(self, method, suffix = '.weights.xml') :
        return os.path.join(self.weightsdir, self.dataloader.name, 'weights', 
                            self.name + '_' + method + suffix)

    def train_factory(self, outputfile) :
        '''Train using TMVA::Factory.'''

        # Make the factory.
        factory = TMVA.Factory(self.name, outputfile, 
                               str(self.factoryoptions))
        factory.SetVerbose(self.verbose)

        methods = self.book_methods(factory)
        
        # Train MVAs
        factory.TrainAllMethods()

        # Test MVAs
        factory.TestAllMethods()

        # Evaluate MVAs
        factory.EvaluateAllMethods()    

        # Save the output.
        outputfile.Close()
    
        print '=== wrote root file {0}\n'.format(outputfile.GetName())
        print '=== TMVAClassification is done!\n'

        weightsfiles = dict((m, self.weights_file(m)) for m in methods)
        classfiles = dict((m, self.weights_file(m, '.class.C')) for m in methods)
        return weightsfiles, classfiles

    def cross_validate(self, nfolds, outputfile) :
        '''Run cross validation with the given number of folds.'''
        crossval = TMVA.CrossValidation(self.dataloader.dataloader)
        crossval.SetNumFolds(nfolds)
        methods = self.book_methods(crossval, self.dataloader.dataloader)
        crossval.Evaluate()
        results = crossval.GetResults()
        return crossval, results

    def cd_weightsdir(self) :
        '''cd to the weightsdir, return the previous working directory.'''
        pwd = os.getcwd()
        if not os.path.exists(self.weightsdir) :
            os.makedirs(self.weightsdir)
        os.chdir(self.weightsdir)
        return pwd

    def train_and_test(self) :
        '''Train and test all methods.'''

        pwd = self.cd_weightsdir()

        # Output file
        outputfile = ROOT.TFile.Open(self.outputfile, 'recreate')

        returnvals = self.train_factory(outputfile)

        # TMVA disables unused branches when copying the trees then doesn't change them back. 
        self.dataloader.backgroundtree.SetBranchStatus('*', 1)
        self.dataloader.signaltree.SetBranchStatus('*', 1)

        os.chdir(pwd)

        return returnvals

    def launch_gui(self) :
        '''Launch the TMVA GUI.'''

        return TMVA.TMVAGui(self.outputfile)
    
class KFoldClassifier(object) :
    '''Runs several TMVAClassifiers with k-folding.'''

    def __init__(self, testingcuts, datakwargs, classifierkwargs) :
        '''testingcuts : the list of cuts to be used for each testing dataset in the folds. The
          training cut for each will be !(testing cut).
        datakwargs : the dict of arguments used to initialise the TMVADataLoaders.
        classifierkwargs : the dict of arguments used to initialise the TMVAClassifiers.
        '''
        self.datakwargs = dict(datakwargs)
        if 'trainingcut' in self.datakwargs :
            del self.datakwargs['trainingcut']
        splitoptions = self.datakwargs.get('splitoptions', TMVADataLoader.default_split_options())
        if isinstance(splitoptions, str) :
            splitoptions = TMVAOptions.from_string(splitoptions)
            self.datakwargs['splitoptions'] = splitoptions
        # Use all available data for each selection.
        splitoptions.update(nTrain_Signal=0,
                            nTrain_Background=0)
        self.classifierkwargs = dict(classifierkwargs)
        self.testingcuts = tuple(testingcuts)
        classifiers = []
        for i, cut in enumerate(self.testingcuts) :
            opts = {'testingcut' : cut}

            datakwargs = dict(self.datakwargs)
            datakwargs['testingcut'] = cut
            data = TMVADataLoader(**datakwargs)

            classifierkwargs = dict(self.classifierkwargs)
            weightsdir = classifierkwargs.get('weightsdir', '')
            weightsdir = '_'.join(filter(None, [weightsdir, 'fold', str(i)]))
            classifierkwargs['weightsdir'] = weightsdir
            classifierkwargs['dataloader'] = data
            opts['classifier'] = TMVAClassifier(**classifierkwargs)

            classifiers.append(opts)
        self.classifiers = tuple(classifiers)

    def train_and_test(self) :
        '''Train and test the classifiers on all folds.'''
        results = []
        for opts in self.classifiers :
            results.append(opts['classifier'].train_and_test())
        return results

    def add_mva(self, inputtree, method, outputfile, outputtree, branchname = None) :
        '''Make a TTree with the MVA values, selecting the weights file according 
        to the fold that each entry belongs to.'''

        foldselectors = [TreeFormula('selform_' + str(i), opts['testingcut'], inputtree) \
                             for i, opts in enumerate(self.classifiers)]
        def select_fold() :
            for i, sel in enumerate(foldselectors) :
                if sel() :
                    return i
            return -1

        mvacalcs = [MVACalc(inputtree, opts['classifier'].weights_file(method), method) \
                        for i, opts in enumerate(self.classifiers)]

        ientry = 0
        def get_mva() :
            i = select_fold()
            if i < 0 :
                return [0.]
            return [mvacalcs[i].calc_mva(ientry)]

        if not branchname :
            branchname = method
        
        outputfile = ROOT.TFile.Open(outputfile, 'recreate')
        outputtree = ROOT.TTree(outputtree, outputtree)
        mvabranch = TreeBranchAdder(outputtree, branchname, get_mva)
        foldbranch = TreeBranchAdder(outputtree, branchname + '_fold', lambda : [select_fold()],
                                     type = 'i')
        for ientry in tree_loop(inputtree) :
            mvabranch.set_value()
            foldbranch.set_value()
            outputtree.Fill()
        outputtree.Write()
        outputfile.Close()
