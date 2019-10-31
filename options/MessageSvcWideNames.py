from Configurables import MessageSvc

width = 30
MessageSvc().Format = '% F%{0}W%S%7W%R%T %0W%M'.format(width)
