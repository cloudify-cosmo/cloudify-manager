(fn [event]
  (do
    (process-policy-triggers)
    (info "processed policy triggers")))
