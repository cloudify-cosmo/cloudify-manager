(fn [event]
  (do
    (execute-workflow* "threshold_exceeded"
                       deployment-id)
    (info "sent execute-workflow")))
