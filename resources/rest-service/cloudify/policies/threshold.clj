(where (and (service #"{{service}}")
            (not (expired? event)))
  (let [inequality (fn [metric]
                     ((threshold-computing/inequality "{{upper_bound}}") metric {{threshold}}))
        downstream (autohealing/downstream* index check-restraints-and-process)]
    (stable {{stability_time}}
      (fn [event] (inequality (:metric event)))
      (where (inequality metric)
        (with {:state EVENT-TRIGGERING-STATE
               :diagnose "{{constants.THRESHOLD_FAILURE}}"}
              downstream)
        (else
          (with :state EVENT-STABLE-STATE downstream))))))
