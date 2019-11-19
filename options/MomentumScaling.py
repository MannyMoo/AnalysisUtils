'''Add momentum scaling.'''

from Configurables import TrackScaleState, DaVinci
DaVinci().UserAlgorithms.insert(0, TrackScaleState())
