(where (and (service #"{{service}}")
            (not (expired? event)))
    (ewma-timeless {{ewma_timeless_r}}
      (where ((autohealing/inequality "{{upper_bound}}") metric {{threshold}})
        (with :state "{{constants.TRIGGERING_STATE}}" downstream)
        (else
          (with :state "{{constants.STABLE_STATE}}" downstream)))))
