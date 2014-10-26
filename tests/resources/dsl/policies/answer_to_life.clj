; events testing is currently almost non-existent for riemann
; so I put these here as symbolic means for testing them
(publish-policy-event "$$$$$$$$$$$$ EVENT 1")
(publish-policy-event "$$$$$$$$$$$$ EVENT 2" :args ["arg1" "arg2"])
(publish-log "^^^^^^^^^^^^ LOG 1")
(publish-log "^^^^^^^^^^^^ LOG 2" :level :error)

(let [downstream (changed-state {:init "pending"}
                  (where (state "ok")
                    process-policy-triggers))]
  (where (metric 42.0)
    (with :state "ok" downstream)
    (else
      (with :state "pending" downstream))))
