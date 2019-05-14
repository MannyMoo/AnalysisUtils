import ROOT, os
from ROOT import TMVA
from AnalysisUtils.treeutils import tree_iter

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

    def __init__(self, signaltree, backgroundtree,
                 methods, variables, spectators = (),
                 weightsdir = '.', outputfile = 'TMVA.root',
                 signalweight = '', backgroundweight = '',
                 signalcut = '', backgroundcut = '',
                 signalglobalweight = 1., backgroundglobalweight = 1.,
                 factoryname = 'TMVAClassification', datasetname = 'dataset',
                 verbose = False,
                 factoryoptions = None,
                 dataoptions = None) :
        '''signaltree : the signal TTree.
        backgroundtree : the background TTree.
        methods : methods to train. Can be a list of method names, in which case the default options
          are used, or a dict of method : options. Here options can be a string or TMVAOptions instance.
        variables : list of training variables. These can just be the variable expressions as strings, or
          a list of arguments to be passed to TMVA.DataLoader.AddVariable.
        spectators : same as variables, for spectator variables which are included in the output but not
          used for training.
        weightsdir : directory in which to save the output.
        outputfile : name of the output file.
        signalweight : expression for the signal weight.
        backgroundweight : expression for the background weight.
        signalcut : selection for the signal.
        backgroundcut : selection for the background.
        signalglobalweight : global weight for signal.
        backgroundglobalweight : global weight for the background.
        factoryname : name of the TMVA.Factory instance.
        datasetname : name of the TMVA.DataLoader instance.
        verbose : if the TMVA.Factory is verbose.
        factoryoptions : options for the TMVA.Factory. If None the default is used.
        dataoptions : options for TMVA.DataLoader.PrepareTrainingAndTestTree. If None the default is used.
        '''

        if not factoryoptions :
            factoryoptions = TMVAClassifier.default_factory_options()
        elif isinstance(factoryoptions, str) :
            factoryoptions = TMVAOptions.from_string(factoryoptions)

        if not dataoptions :
            dataoptions = TMVAClassifier.default_data_options()
        elif isinstance(dataoptions, str) :
            dataoptions = TMVAOptions.from_string(dataoptions)

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
    def default_data_options(*args, **kwargs) :
        '''Get the default DataLoader options, optionally updating them with the given args.'''
        opts = TMVAOptions.from_string('nTrain_Signal=0:nTrain_Background=0:SplitMode=Random:NormMode=NumEvents:!V')
        opts.update(*args, **kwargs)
        return opts

    @staticmethod
    def default_method_options(method, *args, **kwargs) :
        '''Get the default options for the given method, optionally updating them with the given args.'''
        return TMVAOptions.defaultopts[method].copy(*args, **kwargs)

    def make_dataloader(self) :
        '''Make the DataLoader for training.'''

        # Load the data.
        dataloader = TMVA.DataLoader(self.datasetname)

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
        dataloader.AddSignalTree(self.signaltree, self.signalglobalweight)
        dataloader.AddBackgroundTree(self.backgroundtree, self.backgroundglobalweight)

        # Set weight expressions.
        if self.signalweight :
            dataloader.SetSignalWeightExpression(self.signalweight)
        if self.backgroundweight :
            dataloader.SetBackgroundWeightExpression(self.backgroundweight)

        # Prepare the training.
        dataloader.PrepareTrainingAndTestTree(ROOT.TCut(self.signalcut), ROOT.TCut(self.backgroundcut),
                                              str(self.dataoptions))
        
        return dataloader

    def get_method_args(self, dataloader) :
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
        # Could put this in a separate function.
        if any('Cuts' in method for method in methods) :
            print 'Calculating variable ranges.'
            datasetinfo = dataloader.GetDataSetInfo()
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
            
            for method in methods :
                if not 'Cuts' in method :
                    continue
                methods[method][-1].update(cutrangeopts)

        for method, args in methods.items() :
            methods[method] = args[:-1] + (str(args[-1]),)
        return methods

    def book_methods(self, factory, dataloader) :
        '''Book the methods in the given factory.'''
        # Book the methods.
        methods = self.get_method_args(dataloader)
        if isinstance(factory, TMVA.Factory) :
            for method, args in methods.items() :
                print 'Book method', method, 'with options', args[-1]
                factory.BookMethod(dataloader, *args)        
        else :
            for method, args in methods.items() :
                print 'Book method', method, 'with options', args[-1]
                factory.BookMethod(*args)        
        return methods

    def train_factory(self, dataloader, outputfile) :
        '''Train using TMVA::Factory.'''

        # Make the factory.
        factory = TMVA.Factory(self.factoryname, outputfile, 
                               str(self.factoryoptions))
        factory.SetVerbose(self.verbose)

        methods = self.book_methods(factory, dataloader)
        
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

        weightsfiles = dict((m, os.path.join(self.weightsdir, self.datasetname, 'weights', 
                                             self.factoryname + '_' + m + '.weights.xml')) for m in methods)
        classfiles = dict((m, os.path.join(self.weightsdir, self.datasetname, 'weights', 
                                           self.factoryname + '_' + m + '.class.C')) for m in methods)
        return weightsfiles, classfiles

    def cross_validate(self, nfolds, dataloader, outputfile) :
        '''Run cross validation with the given number of folds.'''
        crossval = TMVA.CrossValidation(dataloader)
        crossval.SetNumFolds(nfolds)
        methods = self.book_methods(crossval, dataloader)
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
        dataloader = self.make_dataloader()

        # Output file
        outputfile = ROOT.TFile.Open(self.outputfile, 'recreate')

        returnvals = self.train_factory(dataloader, outputfile)

        # TMVA disables unused branches when copying the trees then doesn't change them back. 
        self.backgroundtree.SetBranchStatus('*', 1)
        self.signaltree.SetBranchStatus('*', 1)

        os.chdir(pwd)

        return returnvals

    def launch_gui(self) :
        '''Launch the TMVA GUI.'''

        return TMVA.TMVAGui(self.outputfile)
    
