import ROOT

def equal_stats_binning(nbins, dataset, variable) :
    '''Get bins 'variable' with equal stats.'''

    if isinstance(variable, ROOT.TObject) :
        variable = variable.GetName()
    vals = sorted(dataset.get(i)[variable].getVal() for i in xrange(dataset.numEntries()))
    nperbin = int(len(vals)/float(nbins))
    bins = [dataset.get(0)[variable].getMin()]
    for i in xrange(1, nbins) :
        icand = i * nperbin
        bins.append((vals[icand] + vals[icand+1])/2.)
    bins.append(dataset.get(0)[variable].getMax())
    return bins
