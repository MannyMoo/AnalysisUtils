'''Tools for weighting TTrees.'''

from __future__ import print_function
import ROOT, os
from AnalysisUtils.selection import AND, OR
from AnalysisUtils.Silence import Silence
from AnalysisUtils.fit import normalised_exp_TF1

def efficiency_weight(var):
    '''Get a weight that's 1/var.'''
    return '{0} > 0. ? 1./{0} : 0.'.format(var)

def efficiency_weight2d(var, vary):
    '''Get a weight that's 1/var/vary.'''
    return '{0} > 0. && {1} > 0. ? 1./{0}/{1} : 0.'.format(var, vary)

def count_zero_weights(weightedtree, weight, originaltree):
    '''Get statistics on the number of entries in weightedtree with zero weights.'''
    vals = {}
    vals['noriginal'] = originaltree.sum_of_weights()
    vals['nweighted'] = weightedtree.sum_of_weights()
    vals['sumweights'] = weightedtree.sum_of_weights(weight = weight)
    vals['nzeroweights'] = weightedtree.GetEntries(AND(weightedtree.selection, '({0}) == 0.'.format(weight)))
    return vals

def get_chi2(hunb, hweighted, chi2opt = 'UW'):
    '''Get the chi2, ndf, & P for the histos being consistent.'''
    with Silence():
        p = hunb.Chi2Test(hweighted, chi2opt)
        chi2 = hunb.Chi2Test(hweighted, chi2opt + 'CHI2')
        chi2ndf = hunb.Chi2Test(hweighted, chi2opt + 'CHI2/NDF')
    ndf = chi2/chi2ndf if chi2ndf > 0 else hunb.GetNbinsX()
    return chi2, ndf, p

def chi2box(hunb, hweighted, chi2opt = 'UW'):
    '''Draw a box with the chi2, NDF & P for the histos being consistent.'''
    chi2, ndf, prob = get_chi2(hunb, hweighted, chi2opt)
    box = ROOT.TPaveText(0.6, 0.902, 1., 1., 'ndc')
    box.SetBorderSize(0)
    box.AddText('#chi^{3}/NDF = {0:5.1f}/{1}, P = {2:4.1f}%'.format(chi2, ndf, prob*100., '{2}'))
    box.SetFillColor(ROOT.kWhite)
    box.SetBorderSize(0)
    box.Draw()
    return box

def fit_expo(h, opt = 'QS'):
    '''Fit a normalised exponential to the histo.'''
    expo = normalised_exp_TF1('expo', h.GetXaxis().GetXmin(), h.GetXaxis().GetXmax(),
                              mean = h.GetMean())
    expo.FixParameter(0, h.Integral('width'))
    expo.SetLineColor(h.GetLineColor())
    result = h.Fit(expo, opt)
    if not result or result.Get().Status() != 0:
        print('WARNING: expo fit failed to', h.GetName())
        return None, None
    return expo.GetParameter(1), expo.GetParError(1)

def validate_weighting(originaltree, weightedtree, name, weight, variables, outputdir,
                       originalname = '', updateoriginal = False, updateweighted = False, chi2opt = 'UW'):
    '''Compare distributions in originaltree to the weighted distributions in weightedtree.'''
    zerocache = weightedtree.get_cache(name + '_ZeroWeights',
                                       ['noriginal', 'nweighted', 'sumweights', 'nzeroweights'],
                                       count_zero_weights, args = (weight, originaltree),
                                       update = (updateweighted or updateoriginal), variables = [weight])
    globalweight = zerocache.noriginal/zerocache.sumweights
    print('{0}: N. entries with zero weight: {1} ({2:.2f}%)'.format(name, zerocache.nzeroweights,
                                                                    100.*zerocache.nzeroweights/zerocache.nweighted))
    selection = weightedtree.get_selection(weight = weight)
    selection = weightedtree.get_selection(selection = selection, weight = str(globalweight))
    caches = {}
    ratios = {}
    canv = ROOT.TCanvas()
    for var in variables:
        _name = name + '_' + var.name
        originalcache = originaltree.histo_cache(var, update = updateoriginal, name = originalname + var.name)
        caches[originalcache.name] = originalcache
        cache = weightedtree.histo_cache(var, selection = selection, name = _name, update = updateweighted)
        caches[cache.name] = cache
        hunb = originalcache.get(0)
        hweighted = cache.get(0)
        for h in hunb, hweighted:
            h.SetLineWidth(3)
            h.SetStats(False)
        hunb.SetLineColor(ROOT.kBlack)
        hweighted.SetLineColor(ROOT.kRed)
        with Silence():
            ratio = ROOT.TRatioPlot(hweighted, hunb)
            ratio.SetH1DrawOpt('E')
            ratio.Draw()
        ratio.GetUpperPad().SetLogy()
        box = chi2box(hunb, hweighted, chi2opt)
        print(_name, box.GetLine(0).GetTitle())
        canv.SaveAs(os.path.join(outputdir, _name + '_corrected_ratio.pdf'))
        if 'time' in var.name:
            unbtau, unbtauerr = fit_expo(hunb)
            tau, tauerr = fit_expo(hweighted)
            delta = tau - unbtau
            deltaerr = (unbtauerr**2 + tauerr**2)**.5
            sigma = delta/deltaerr
            print('Tau = {0:.3f} +/- {1:.3f} ps, dTau = {2:.1f} +/- {3:.1f} fs ({4:.2f} sigma)'\
                .format(tau, tauerr, delta*1000., deltaerr*1000., sigma))
        ratios[_name] = ratio
    return caches, ratios

def get_weights_and_vals(tree, variables, n = None):
    '''Get weights (from the selection) and values of the variables from the tree.'''
    weightvar = tree.selection_functor()
    varlist = tree.get_functor_list(variables)
    weights = []
    vals = []
    if None == n:
        for i in tree:
            weights.append(weightvar())
            vals.append(vals())
    else:
        j = 0
        for i in tree:
            weights.append(weightvar())
            vals.append(varlist())
            j += 1
            if j >= n:
                break
    return weights, vals
    
def gbreweight(weighttree, originaltree, name, variables, n = None):
    '''Use Hep_ml GBReweighter to calculate weights for weighttree to match originaltree in the given variables.
    Adds a friend with branch named 'name' of length 2: the first element is the calculated weight, the second is
    the product of that weight with any existing weight used for the weighttree (from the selection).'''
    from hep_ml.reweight import GBReweighter
    
    originalweights, originalvals = get_weights_and_vals(originaltree, variables, n)
    weightedweights, weightedvals = get_weights_and_vals(weighttree, variables, n)
    
    weighter = GBReweighter()
    print('Fit GBReweighter', name)
    weighter.fit(original = originalvals, original_weight = originalweights, target = weightedvals,
                 target_weight = weightedweights)
    weight = weighttree.selection_functor()
    vals = weighttree.get_functor_list(variables)
    def get_weight():
        _w = weighter.predict_weights([vals()])[0]
        return [_w, _w * weight()]
    print('Add weights for GBReweighter', name)
    weighttree.add_friend_tree(name, {name : dict(function = get_weight, length = 2)})

def ratio_histo(weighttree, originaltree, name, variable, variableY = None, variableZ = None):
    '''Get a histogram of the ratio of variables between trees.'''
    horiginal = originaltree.draw(var = variable, varY = variableY, varZ = variableZ,
                                  name = originaltree.name + '_' + name + '_original')
    hunweighted = weighttree.draw(var = variable, varY = variableY, varZ = variableZ,
                                  name = weighttree.name + '_' + name + '_unweighted')
    hratio = horiginal.Clone()
    hratio.SetName(name + '_ratio')
    hratio.Divide(hunweighted)
    return {'horiginal' : horiginal, 'hunweighted' : hunweighted, 'hratio' : hratio}    

def histo_reweight(weighttree, originaltree, name, variable, variableY = None, variableZ = None):
    '''Make a histo of the given variable for each tree and use the ratio to reweight weighttree.
    Adds a friend with branch named 'name' of length 2: the first element is the calculated weight, the second is
    the product of that weight with any existing weight used for the weighttree (from the selection).'''

    histos = ratio_histo(weighttree, originaltree, name, variable = variable, variableY = variableY,
                         variableZ = variableZ)
    add_histo_weight(weighttree, histos['hratio'], name, variable = variable, variableY = variableY, 
                     variableZ = variableZ)
    return histos

def add_histo_weight(weighttree, hratio, name, variable, variableY = None, variableZ = None, n = None):
    '''Add a weight from a histogram.'''
    variables = filter(None, [variable, variableY, variableZ])
    variables = weighttree.get_functor_list(variables)
    selvar = weighttree.selection_functor()
    def get_ratio():
        vals = variables()
        #bins = [ax.FindBin(v) for v, ax in zip(vals, [hratio.GetXaxis(), hratio.GetYaxis(), hratio.GetZaxis()])]
        #ratio = hratio.GetBinContent(*bins)
        with Silence():
            ratio = hratio.Interpolate(*vals)
        return [ratio, ratio*selvar()]
    weighttree.add_friend_tree(name, {name : dict(function = get_ratio, length = 2)})
    return {'success' : True}
