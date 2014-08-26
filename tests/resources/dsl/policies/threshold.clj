(where (service "{{metric}}")
  (let [upper-bound (parse-boolean "{{upper_bound}}")
        inequality (if upper-bound >= <=)
        downstream (sdo (changed-state {:init "ok"}
                          (where (state "threshold_breached")
                            process-policy-triggers))
                        index)]
    (where (inequality metric {{threshold}})
      (with :state "threshold_breached" downstream)
      (else
        (with :state "ok" downstream)))))
