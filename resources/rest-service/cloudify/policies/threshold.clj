(where (service "{{service}}")
  (letfn [(inequality [metric]
            ((autohealing/inequality "{{upper_bound}}") metric {{threshold}}))]
    (stable {{stability_time}}
      (fn [event] (inequality (:metric event)))
      (where (inequality metric)
        (with :state "{{constants.TRIGGERING_STATE}}" downstream)
        (else
          (with :state "{{constants.STABLE_STATE}}" downstream))))))
