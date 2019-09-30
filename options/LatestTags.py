from Configurables import DaVinci, CondDB

CondDB().LatestGlobalTagByDataType = DaVinci().getProp('DataType')
