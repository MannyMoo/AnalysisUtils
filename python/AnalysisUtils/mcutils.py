'''MC utilities.'''

def add_velo_track_assoc(inputtype = 'DST') :
    '''Add associator for FittedHLT1VeloTracks which are used to make PVs (needs LDST).'''

    inputtype = inputtype.lower()
    # VELO tracks aren't saved, so no point adding associators.
    if inputtype == 'mdst':
        return

    from Configurables import LoKi__Track2MC, DaVinci

    ldst = (inputtype == 'ldst')
    lokitrassoc = LoKi__Track2MC()
    lokitrassoc.Tracks = ['Rec/Track/FittedHLT1VeloTracks']
    DaVinci().UserAlgorithms.insert(0, lokitrassoc)
    if ldst:
        from Configurables import TrackAssociator
        tr = TrackAssociator(TracksInContainer = 'Rec/Track/FittedHLT1VeloTracks')
        DaVinci().UserAlgorithms.insert(0, tr)
    else:
        from Configurables import ProxyTrackAssociator, DaVinci
        
        velotrassoc = ProxyTrackAssociator()
        velotrassoc.InputTracks = 'Rec/Track/FittedHLT1VeloTracks'
        DaVinci().UserAlgorithms.insert(0, velotrassoc)
