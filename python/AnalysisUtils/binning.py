import ROOT
from math import exp, log

def equal_stats_binning(nbins, seq, minval = None, maxval = None):
    '''Get bins with equal statistics from the given sequence of floats.'''
    # Could do this more efficiently with std::lower_bound
    vals = sorted(seq)
    if minval == None:
        minval = min(vals)
    if maxval == None:
        maxval = max(vals)
    nperbin = int(len(vals)/float(nbins))
    bins = [minval]
    istart = -1
    iend = nperbin
    for i in xrange(1, nbins) :
        istart = i-1
        iend = i + nperbin
        bins.append((vals[iend] + vals[iend+1])/2.)
        vals[istart:iend] = [vals[istart:iend]]
    vals[istart+1:] = [vals[istart+1:]]
    bins.append(maxval)
    return bins, vals

def roo_equal_stats_binning(nbins, dataset, variable) :
    '''Get bins in 'variable' with equal stats.'''

    if isinstance(variable, ROOT.TObject) :
        variable = variable.GetName()
    return equal_stats_binning(nbins, (dataset.get(i)[variable].getVal() for i in xrange(dataset.numEntries())),
                               dataset.get(0)[variable].getMin(), dataset.get(0)[variable].getMax())

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
