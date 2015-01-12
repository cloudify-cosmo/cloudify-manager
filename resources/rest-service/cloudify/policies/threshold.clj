(where (and (service #"{{service}}")
            (not (expired? event)))
  (let [inequality (fn [metric]
                     ((threshold-computing/inequality "{{upper_bound}}") metric {{threshold}}))
        downstream
          (autohealing/downstream* index
                                   (check-restraints-and-process workflow-trigger-restraints))]
    (stable {{stability_time}}
      (fn [event] (inequality (:metric event)))
      (where (inequality metric)
        (with :state EVENT-TRIGGERING-STATE downstream)
        (else
          (with :state EVENT-STABLE-STATE downstream))))))
