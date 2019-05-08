import ROOT
from AnalysisUtils.treeutils import random_string, TreeFormula, TreeBranchAdder, tree_loop

def multi_gauss(workspace, name, variable, mean, sigmas, sigmamax, sigmaerror = 0.5,
                fracerror = 0.05, meanwindow = 100., meanerror = 1.) :
    if not isinstance(mean, ROOT.RooAbsReal) :
        mean = workspace.roovar(name + '_mean', val = mean,
                                xmin = mean - meanwindow, xmax = mean + meanwindow,
                                error = meanerror)
    # Single Gaussian.
    if not isinstance(sigmas, (tuple, list)) :
        return workspace.factory('RooGaussian', name, variable, mean, 
                                 workspace.roovar(name + '_sigma_0', val = sigmas,
                                                  xmin = 0., xmax = sigmamax,
                                                  error = sigmaerror))

    firstfrac, firstsigma = sigmas[0]
    firstfrac = workspace.roovar(name + '_frac_0', val = firstfrac, xmin = 0., xmax = 1.,
                                 error = fracerror)
    firstsigma = workspace.roovar(name + '_sigma_0', val = firstsigma, xmin = 0., xmax = sigmamax,
                                  error = sigmaerror)
    firstpdf = workspace.factory('RooGaussian', name + '_0', variable, mean, firstsigma)
    pdfs = [(firstfrac, firstpdf)]
    prevsigma = firstsigma
    i = 0
    for i, (frac, sig) in enumerate(sigmas[1:-1]) :
        istr = str(i+1)
        frac = workspace.roovar(name + '_frac_' + istr, val = frac, xmin = 0., xmax = 1., error = fracerror)
        diff = workspace.roovar(name + '_sigma_diff_' + istr, val = sig - prevsigma.getVal(),
                                xmin = 0., xmax = sigmamax, error = sigmaerror)
        sigma = workspace.factory('sum', name + '_sigma_' + istr, prevsigma, diff)
        pdf = workspace.factory('RooGaussian', name + '_' + istr, variable, mean, sigma)
        pdfs.append((frac, pdf))
        prevsigma = sigma
    sig = sigmas[-1]
    istr = str(len(sigmas)-1)
    diff = workspace.roovar(name + '_sigma_diff_' + istr, val = sig - prevsigma.getVal(),
                            xmin = 0., xmax = sigmamax, error = sigmaerror)
    sigma = workspace.factory('sum', name + '_sigma_' + istr, prevsigma, diff)
    lastpdf = workspace.factory('RooGaussian', name + '_' + istr, variable, mean, sigma)
    
    sumpdf = workspace.factory('RSUM', name,
                               *([frac.GetName() + '*' + pdf.GetName() for frac, pdf in pdfs] + [lastpdf.GetName()]))
    return sumpdf

def integral(pdf, variable, xmin, xmax) :
    '''Get the integral of a PDF in the given variable between xmin and xmax.'''
    variable = variable.Clone()
    rangename = 'range_' + random_string()
    variable.setRange(rangename, xmin, xmax)
    args = ROOT.RooArgSet(variable)
    integrator = pdf.createIntegral(args, rangename)
    return integrator.getVal()

def sideband_subtraction_weight(pdf, variable, signalmin, signalmax, bkgmin, bkgmax,
                                extrabkgints = (), extrasigints = ()) :
    '''Calculate the sideband subtraction weight using the given PDF and variable,
    signal range and background range. Optionally, additional ranges can be given
    for signal and background, which should be sequences of pairs.'''

    signalints = [(signalmin, signalmax)] + list(extrasigints)
    bkgints = [(bkgmin, bkgmax)] + list(extrabkgints)
    
    signalint = sum(integral(pdf, variable, xmin, xmax) for xmin, xmax in signalints)
    bkgint = sum(integral(pdf, variable, xmin, xmax) for xmin, xmax in bkgints)
    return -signalint/bkgint

def add_sideband_subtraction_weights(datalib, datasetname, treename, branchname,
                                     pdf, variable, signalmin, signalmax, bkgmin, bkgmax,
                                     extrabkgints = (), extrasigints = (),
                                     datasetsel = 'inrange_all && selection_pass') :
    '''Add sideband subtraction weights to a dataset using the given PDF, variable and ranges.'''

    signalints = [(signalmin, signalmax)] + list(extrasigints)
    bkgints = [(bkgmin, bkgmax)] + list(extrabkgints)

    sidebandweight = sideband_subtraction_weight(pdf, variable, signalmin, signalmax, bkgmin, bkgmax,
                                                 extrabkgints, extrasigints)

    tree = datalib.get_data(datasetname)
    treevar = TreeFormula(variable.GetName(), variable.GetName(), tree)
    selvar = TreeFormula('sel_' + random_string(), datasetsel, tree)
    
    foutname = datalib.friend_file_name(datasetname, treename, treename, makedir = True)
    fout = ROOT.TFile.Open(foutname, 'recreate')
    treeout = ROOT.TTree(treename, treename)
    weight = 0.
    weightbranch = TreeBranchAdder(treeout, branchname, lambda : [weight])
    
    for i in tree_loop(tree) :
        val = treevar()
        if not selvar() :
            weight = 0.
        elif any(xmin <= val < xmax for xmin, xmax in signalints) :
            weight = 1.
        elif any(xmin <= val < xmax for xmin, xmax in bkgints) :
            weight = sidebandweight
        else :
            weight = 0.
        weightbranch.set_value()
        treeout.Fill()
    treeout.Write()
    fout.Close()
