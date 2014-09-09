(let [downstream (changed-state {:init "pending"}
                  (where (state "ok")
                    process-policy-triggers))]
  (where (metric 42.0)
    (with :state "ok" downstream)
    (else
      (with :state "pending" downstream))))
