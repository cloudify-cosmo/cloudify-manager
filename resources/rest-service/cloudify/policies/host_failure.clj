(where* expired? (fn [event] ((with {:failing_node (:node_id event) :diagnose "heart-beat-failure"} process-policy-triggers) event )))
