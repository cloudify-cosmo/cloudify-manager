;(where (service "{{metric}}")
;  (let [upper-bound (parse-boolean "{{upper_bound}}")
;        inequality (if upper-bound >= <=)
;        downstream (sdo (changed-state {:init "ok"}
;                          (where (state "threshold_breached")
;                            process-policy-triggers))
;                        index)]
;    (where (inequality metric {{threshold}})
;      (with :state "threshold_breached" downstream)
;      (else
;        (with :state "ok" downstream)))))
;
;(let [downstream (changed-state {:init "pending"}
;                  (where (state "ok")
;                    process-policy-triggers))]
;  (where (metric 42.0)
;    (with :state "ok" downstream)
;    (else
;      (with :state "pending" downstream))))
;
(where expired)
  (process-policy-triggers)
