import ROOT
from math import exp, log

def equal_stats_binning(nbins, dataset, variable) :
    '''Get bins in 'variable' with equal stats.'''

    if isinstance(variable, ROOT.TObject) :
        variable = variable.GetName()
    vals = sorted(dataset.get(i)[variable].getVal() for i in xrange(dataset.numEntries()))
    nperbin = int(len(vals)/float(nbins))
    bins = [dataset.get(0)[variable].getMin()]
    istart = -1
    iend = nperbin
    for i in xrange(1, nbins) :
        istart = i-1
        iend = i + nperbin
        bins.append((vals[iend] + vals[iend+1])/2.)
        vals[istart:iend] = [vals[istart:iend]]
    vals[istart+1:] = [vals[istart+1:]]
    bins.append(dataset.get(0)[variable].getMax())
    return bins, vals

def exponential_binning(nbins, tmin, tmax, tau) :
    '''Get bins with exponentially increasing width.'''
    rangeint = exp(-tmin/tau) - exp(-tmax/tau)
    binarea = rangeint/nbins
    bins = [tmin]
    for i in xrange(1, nbins+1) :
        try :
            bins.append(bins[-1] - tau * log(1. - exp(bins[-1]/tau)*binarea))
        except :
            bins.append(tmax)
            break
    return bins
