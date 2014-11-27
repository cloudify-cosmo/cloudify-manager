(where* (is-service-name-in {%for s in service%} "{{s}}" {%endfor%})
  (where* expired?
          (fn [event]
            ((with {:failing_node (:node_id event)
                    :diagnose "{{constants.HEART_BEAT_FAILURE}}"
                    :state "{{constants.TRIGGERING_STATE}}"}
                   downstream)
             event))))
