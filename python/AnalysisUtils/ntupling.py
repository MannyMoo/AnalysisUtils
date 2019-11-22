from DecayTreeTuple.Configuration import DecayTreeTuple
from Configurables import MCDecayTreeTuple
from AnalysisUtils.Selections.mcselections import build_mc_unbiased_selection
from AnalysisUtils.ntuplling import add_velo_track_assoc

def _make_tuple(desc, suff, ToolList, TupleType, arrow = '->', **kwargs) :
    dtt = TupleType(desc.get_full_alias() + suff, **kwargs)
    dtt.ToolList = list(ToolList)
    dtt.Decay = desc.to_string(carets = True, arrow = arrow)
    if dtt.getProp('UseLabXSyntax') :
        aliases = desc.get_aliases()
        desc.set_labX_aliases()
    dtt.addBranches(desc.branches())
    if dtt.getProp('UseLabXSyntax') :
        desc.set_aliases(aliases)

    return dtt

def make_tuple(desc, inputloc, 
               ToolList = ['TupleToolPrimaries',
                           'TupleToolGeometry',
                           'TupleToolPid',
                           'TupleToolANNPID',
                           'TupleToolRecoStats',
                           'TupleToolKinematic',
                           'TupleToolEventInfo',
                           'TupleToolTrackInfo'],
               suff = '_Tuple',
               **kwargs) :
    dtt = _make_tuple(desc, suff, ToolList, DecayTreeTuple, **kwargs)
    dtt.Inputs = [inputloc]
    return dtt

def make_mc_tuple(desc, ToolList = ['MCTupleToolKinematic', 'TupleToolEventInfo'],
                  suff = '_MCDecayTreeTuple', arrow = '==>', **kwargs) :
    return _make_tuple(desc, suff, ToolList, MCDecayTreeTuple, arrow, **kwargs)
