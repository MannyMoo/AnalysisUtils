'''Utilities for plotting output.'''

import ROOT, subprocess

# Colours, marker and line styles for histos, so you can assign them in a loop.
goodcolours = (ROOT.kBlack, ROOT.kBlue, ROOT.kRed, ROOT.kGreen+2, ROOT.kMagenta+1, ROOT.kCyan+1,
               ROOT.kOrange+1, ROOT.kYellow+1, ROOT.kGray+2)
goodcolors = goodcolours
goodmarkers = (ROOT.kPlus, ROOT.kStar, ROOT.kCircle, ROOT.kMultiply, ROOT.kFullDotLarge,
               ROOT.kFullSquare, ROOT.kFullTriangleUp, ROOT.kFullTriangleDown, ROOT.kOpenCircle,
               ROOT.kOpenSquare, ROOT.kOpenTriangleUp, ROOT.kOpenDiamond, ROOT.kOpenCross,
               ROOT.kOpenStar, ROOT.kFullStar)
goodlinestyles = tuple(range(1, 11))

def plot_fit(pdf, data, plotVar = None, pullCanvHeight = 0.2, canvArgs = (),
             dataPlotArgs = (), components = (), legpos = (0.7, 0.7, 0.95, 0.95)) :
    '''Plot the fit over the data for the given plotVar with the pull below. If
    pullCanvHeight == 0. the pull isn't drawn. If pdf.extendMode() is True, the fit PDF
    is normalised according to the fitted yields of the extended PDF, else it's
    normalised to the data. canvArgs are passed to the TCanvas constructor.'''

    if not plotVar :
        plotVars = pdf.getObservables(data)
        if len(plotVars) > 1 :
            print 'Sorry, only 1D plotting is implemented so far!'
            return

        plotVar = plotVars.first()

    try :
        canv = ROOT.TCanvas(*canvArgs)
    except :
        print 'Failed to construct TCanvas with args', repr(canvArgs)
        raise

    canv.cd()
    mainPad = ROOT.TPad('mainPad', 'mainPad', 0., pullCanvHeight, 1., 1.)
    mainPad.SetMargin(0.12, 0.05, 0.05, 0.1)
    mainPad.Draw()

    mainFrame = plotVar.frame()
    data.plotOn(mainFrame, *dataPlotArgs)
    leg = None
    legentries = []
    if components :
        names = filter(None, (filter(lambda arg : arg.GetName() == 'Name', comp) for comp in components))
        if names :
            leg = ROOT.TLegend(*legpos)
        for component in components :
            compplot = pdf.plotOn(mainFrame, *component)
            compname = filter(lambda arg : arg.GetName() == 'Name', component)
            legentries.append([compplot, compname[0].getString(0)])
    # if hasattr(pdf, 'extendMode') and pdf.extendMode() != 0 :
    #     # Change from RooAbsReal.RelativeExtended, as given in the manual, as it doesn't
    #     # exist.
    #     pdf.plotOn(mainFrame, ROOT.RooFit.Normalization(1.0, ROOT.RooAbsReal.RelativeExpected))
    # else :
    pdf.plotOn(mainFrame)

    mainPad.cd()
    mainFrame.Draw()
    if leg :
        for compplot, name in legentries :
            leg.AddEntry(name, name)
        leg.Draw()
    hdata = filter(lambda prim : isinstance(prim, ROOT.TH1), mainPad.GetListOfPrimitives())[0]
    hdata.SetTitle('')
    hdata.GetXaxis().SetTitleSize(0.05)
    hdata.GetYaxis().SetTitleSize(0.05)
    hdata.GetXaxis().SetLabelSize(0.05)
    hdata.GetYaxis().SetLabelSize(0.05)
    hdata.GetYaxis().SetTitleOffset(1.05)
    mainPad.Update()

    if pullCanvHeight <= 0. :
        return locals()

    canv.cd()
    pullPad = ROOT.TPad('mainPad', 'mainPad', 0., 0., 1., pullCanvHeight)
    pullPad.SetMargin(0.12, 0.05, 0.05, 0.1)
    pullPad.Draw()

    # from /opt/local/share/root5/doc/root/tutorials/roofit/rf109_chi2residpull.C
    pullFrame = plotVar.frame()
    pullHist = mainFrame.pullHist()
    pullFrame.addPlotable(pullHist, 'P')
    pullPad.cd()
    pullFrame.Draw()
    pullHist = filter(lambda prim : isinstance(prim, ROOT.TH1), pullPad.GetListOfPrimitives())[0]
    pullHist.GetYaxis().SetRangeUser(-5., 5.)
    pullHist.SetTitle('')
    pullHist.GetXaxis().SetTitle('')
    pullHist.GetXaxis().SetLabelSize(0.)
    pullHist.GetXaxis().SetTickLength(0.1)
    pullHist.GetYaxis().SetLabelSize(0.15)
    pullHist.GetYaxis().SetNdivisions(5)
    #pullHist.GetYaxis().SetTickLength(0.1)
    pullHist.GetYaxis().SetTitle('Pull')
    pullHist.GetYaxis().SetTitleSize(0.2)
    pullHist.GetYaxis().SetTitleOffset(0.2)
    pullHist.GetYaxis().CenterTitle()
    return locals()

def save_eps(canv, name) :
    '''Save as .eps and remove the CreationDate line to avoid spurious diffs in git.'''

    if not name.endswith('.eps') :
        name += '.eps'
    canv.SaveAs(name)
    subprocess.call(['sed', '-i', '/CreationDate/d', name])

def get_y_minmax(histo, witherrs = True):
    '''Get the min & max y value of a histo or sequence of histos, optionally including
    the range of the bin errors.'''
    if not isinstance(histo, ROOT.TH1):
        vals = tuple(get_y_minmax(h, witherrs) for h in histo)
        ymin = min(v[0] for v in vals)
        ymax = max(v[1] for v in vals)
        return ymin, ymax

    if witherrs:
        ymin = min(histo.GetBinContent(i) - histo.GetBinError(i) for i in xrange(histo.GetNbinsX()))
        ymax = max(histo.GetBinContent(i) + histo.GetBinError(i) for i in xrange(histo.GetNbinsX()))
    else:
        ymin = min(histo.GetBinContent(i) for i in xrange(histo.GetNbinsX()))
        ymax = max(histo.GetBinContent(i) for i in xrange(histo.GetNbinsX()))
    return ymin, ymax

def set_y_range(histo, padding = 0.1, symmetric = False):
    '''Set the y range of a histo or sequence of histos, padding with a fraction of the max - min range,
    optionally symmetric about zero.'''

    ymin, ymax = get_y_minmax(histo)
    if symmetric:
        ymax = max(abs(ymin), abs(ymax))
        ymin = -ymax
    yrange = ymax - ymin
    ymax += padding * yrange
    ymin -= padding * yrange

    if not isinstance(histo, ROOT.TH1):
        for h in histo:
            h.GetYaxis().SetRangeUser(ymin, ymax)
    else:
        histo.GetYaxis().SetRangeUser(ymin, ymax)
    return ymin, ymax
