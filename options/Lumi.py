from Configurables import DaVinci

DaVinci().Lumi = (not DaVinci().getProp('Simulation'))
