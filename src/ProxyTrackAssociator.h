#ifndef PROXYTRACKASSOCIATOR_H
#define PROXYTRACKASSOCIATOR_H 1

#include <GaudiKernel/Property.h>
#include <GaudiAlg/GaudiAlgorithm.h>
#include <GaudiKernel/AlgFactory.h>
#include <GaudiKernel/DeclareFactoryEntries.h>

/** @class ProxyTrackAssociator
 *
 * Create MC links for tracks that don't have them by first associating them by
 * LHCbIDs to tracks that do have MC links.
 * 
 * Note that this is a bit of a dirty hack and shouldn't be used for any 
 * rigorous ghost rate or efficiency studies, especially if you don't get a 
 * 100 % efficiency in track -> track associations.
 * 
 *
 *  @author Michael Alexander
 *  @date 2018-05-11
 */

class ProxyTrackAssociator : public GaudiAlgorithm
{
 public:
  // ========================================================================
  using GaudiAlgorithm::GaudiAlgorithm;
  /// execution of the algorithm
  StatusCode execute() override;
  // ========================================================================
 protected:
  Gaudi::Property<std::string> m_inputtracks{this, "InputTracks", "", "Tracks for which to build the MC links."} ;
  Gaudi::Property<float> m_matchfrac{this, "TrackMatchFrac", 0.7, 
      "Fraction of LHCbIDs in the input track that need to be a linked track in order for them to be associated."} ;
  Gaudi::Property<std::vector<std::string>> m_linkedtracks{this, "LinkedTracks", {"Rec/Track/Best"}, 
      "List of tracks with MC links to be associated to."} ;
} ;

#endif
