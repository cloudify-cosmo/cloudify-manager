(fn [event]
  (execute-workflow "threshold_exceeded"
                    deployment-id
                    {:parameters {:param1 "value"}}))
