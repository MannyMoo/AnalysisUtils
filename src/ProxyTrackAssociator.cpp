#include "ProxyTrackAssociator.h"
#include <Relations/RelationWeighted.h>
#include <Event/Track.h>
#include <Linker/LinkedTo.h>
#include <Linker/LinkerWithKey.h>
#include <Event/MCParticle.h>

DECLARE_COMPONENT( ProxyTrackAssociator )

StatusCode ProxyTrackAssociator::execute() {
  // Get the input tracks to be linked.
  const LHCb::Tracks* inputtracks = getIfExists<LHCb::Tracks>(m_inputtracks) ;
  if(nullptr == inputtracks){
    Warning("No tracks at " + m_inputtracks + "!") ;
    return StatusCode::SUCCESS ;
  }

  // Get the tracks that have links, and their linkers.
  typedef LinkedTo<LHCb::MCParticle, LHCb::Track> Linker ;
  std::map<std::string, const LHCb::Tracks*> linkedtracks ;
  std::map<std::string, Linker*> linkers ;
  for(const auto& location : m_linkedtracks) {
    Linker* linker = new Linker(evtSvc() , msgSvc(), location) ;
    if(linker->notFound()){
      Warning("MC links for tracks at " + location + " not found!") ;
      delete linker ;
      continue ;
    }
    linkers[location] = linker ;

    const LHCb::Tracks* theselinkedtracks = getIfExists<LHCb::Tracks>(location) ;
    if(nullptr == theselinkedtracks){
      Warning("No tracks at " + location + "!") ;
      continue ;
    }
    linkedtracks[location] = theselinkedtracks ;
  }
  if(linkedtracks.empty() || linkers.empty()){
    Warning("Didn't find any tracks with MC links!") ;
    return StatusCode::SUCCESS ;
  }

  // Build the relations table of input track -> tracks with links.
  Relations::RelationWeighted<LHCb::Track, LHCb::Track, unsigned int> tracktotrackrelations(100) ;
  for(const auto& inputtrack : *inputtracks){
    unsigned int nmatched(0) ;
    for(const auto& location : m_linkedtracks) {
      for(const auto& linkedtrack : *linkedtracks[location]){
	unsigned int nmatch = inputtrack->nCommonLhcbIDs(*linkedtrack) ;
	float matchfrac = float(nmatch)/inputtrack->nLHCbIDs() ;
	if(matchfrac < m_matchfrac)
	  continue ;
	counter("Track match fractions") += matchfrac ;
	tracktotrackrelations.i_relate(inputtrack, linkedtrack, matchfrac) ;
	++nmatched ;
      }
    }
    counter("Linked tracks") += (nmatched > 0) ;
    counter("N. track matches per input track") += nmatched ;
  }

  // Link the input tracks to the MCParticles of their associated tracks.
  LinkerWithKey<LHCb::MCParticle,LHCb::Track> outputlinks(evtSvc(), msgSvc(), m_inputtracks) ;
  for(const auto& inputtrack : *inputtracks){
    auto trackrelations = tracktotrackrelations.relations(inputtrack) ;
    // Loop over the related tracks.
    std::map<const LHCb::MCParticle*, float> mcpweights ;
    for(const auto& trackrelation : trackrelations){
      LHCb::Track* linktrack = trackrelation.to() ;
      std::vector<std::string>::const_iterator ilocation = m_linkedtracks.begin() ;
      for( ; ilocation != m_linkedtracks.end() ; ++ilocation){
	if(std::find(linkedtracks[*ilocation]->begin(),
		     linkedtracks[*ilocation]->end(),
		     linktrack) != linkedtracks[*ilocation]->end())
	  break ;
      }
      Linker& linker = *linkers[*ilocation] ;
      const LHCb::MCParticle* mcp = linker.first(linktrack) ;
      // Add the link with weight given by the product of the track -> track and track -> MCParticle weights.
      // Check first if it's already in the link table, in which case take the greatest weight.
      while(0 != mcp){
	float weight = linker.weight() * trackrelation.weight() ;
	if(mcpweights.find(mcp) == mcpweights.end())
	  mcpweights[mcp] = weight ;
	else 
	  mcpweights[mcp] = std::max(weight, mcpweights[mcp]) ;
	mcp = linker.next() ;
      }
    }
    // Add the links.
    counter("N. MCParticle links per input track") += mcpweights.size() ;
    for(const auto& mcpweight : mcpweights){
      outputlinks.link(inputtrack, mcpweight.first, mcpweight.second) ;
      counter("MCParticle match fractions") += mcpweight.second ;
    }
  }
  for(auto& ilinker : linkers)
    delete ilinker.second ;

  return StatusCode::SUCCESS ;
}
