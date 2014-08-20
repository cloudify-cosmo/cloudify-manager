(fn execute-workflow
  [ctx]
    (let [deployment-id       (:deployemnt_id ctx)
          manager-ip          "127.0.0.1"
          manager-rest-port   8100
          base-uri            (str "http://" manager-ip ":" manager-rest-port)
          endpoint            (str "/deployments/" deployment-id "/executions")
          resource-uri        (str base-uri endpoint)
          parameters          (:parameters ctx)
          workflow            (:workflow parameters)
          workflow-parameters (:workflow_parameters parameters)
          body                (cheshire/generate-string {:workflow_id workflow
                                                         :parameters workflow-parameters})]
      (http/post resource-uri
        {:content-type   :json
         :accept         :json
         :socket-timeout (:socket_timeout parameters)
         :conn-timeout   (:conn_timeout parameters)
         :body           body})))
