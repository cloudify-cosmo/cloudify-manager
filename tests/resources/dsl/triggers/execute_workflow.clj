(fn execute-workflow
  [ctx]
    (let [deployment-id         (:deployment-id ctx)
          manager-ip            (or (System/getenv "MANAGEMENT_IP") "127.0.0.1")
          raw-manager-rest-port (or (System/getenv "MANAGER_REST_PORT") "80")
          manager-rest-port     (Integer/parseInt raw-manager-rest-port)
          base-uri              (str "http://" manager-ip ":" manager-rest-port)
          endpoint              (str "/deployments/" deployment-id "/executions")
          resource-uri          (str base-uri endpoint)
          parameters            (:parameters ctx)
          workflow              (:workflow parameters)
          workflow-parameters   (:workflow_parameters parameters)
          body                  (cheshire.core/generate-string {:workflow_id workflow
                                                              :parameters workflow-parameters})]
      (clj-http.client/post resource-uri
        {:content-type   :json
         :accept         :json
         :socket-timeout (:socket_timeout parameters)
         :conn-timeout   (:conn_timeout parameters)
         :body           body})))
