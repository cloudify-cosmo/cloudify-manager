; $node_id will be injected with the current node id
; $event will be injected with a json form event

(fn [evnt]
  (let [reachable-event (assoc evnt :host "$node_id"
                                    :service "performance"
                                    :state ""
                                    :description "$event"
                                    :tags ["cosmo"])]
      (call-rescue reachable-event [index])))
