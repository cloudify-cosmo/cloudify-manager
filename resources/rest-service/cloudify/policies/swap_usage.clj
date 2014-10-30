(let [downstream (changed-state {:init "ok"}
                  (where (state "swap_threshold_breached")
                    process-policy-triggers))]
  (where (>= metric (double {{swap_threshold}}))
    (fn [event]
      ((with {:state "swap_threshold_breached"
              :diagnose "swap_in_use"
              :failing_node (:node_id event)}
          downstream)
       event))
    (else
      (with :state "ok" downstream))))
