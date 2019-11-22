from AnalysisUtils.mcutils import add_velo_track_assoc
from Configurables import DaVinci

add_velo_track_assoc(DaVinci().getProp('InputType'))
