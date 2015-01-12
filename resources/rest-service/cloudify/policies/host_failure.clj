(where* (is-service-name-contained {%for s in service%} "{{s}}" {%endfor%})
  (let [downstream
         (autohealing/downstream* index
                                  (check-restraints-and-process workflow-trigger-restraints))]
    (where* expired?
            (fn [event]
              ((with {:failing_node (:node_id event)
                      :diagnose "{{constants.HEART_BEAT_FAILURE}}"
                      :state EVENT-TRIGGERING-STATE}
                     downstream)
               event)))))
