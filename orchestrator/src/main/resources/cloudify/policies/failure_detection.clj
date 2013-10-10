; $node_id will be injected with the current node id
; $event will be injected with a json form event

(fn [evnt]
  (let [ip-event (assoc evnt :host "$node_id"
                             :service "ip"
                             :state (get evnt :host)
                             :description "$event"
                             :tags ["cosmo"])]
      (call-rescue ip-event [index]))
  (let [reachable-event (assoc evnt :host "$node_id"
                                    :service "reachable"
                                    :state "false"
                                    :description "$event"
                                    :tags ["cosmo"])]
      (call-rescue reachable-event [index])))
