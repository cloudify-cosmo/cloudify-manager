(fn execute-workflow
  [ctx]
    (let [deployment-id         (:deployment_id ctx)
          parameters            (:trigger-parameters ctx)
          manager-ip            (or (System/getenv "MANAGEMENT_IP") "127.0.0.1")
          raw-manager-rest-port (or (System/getenv "MANAGER_REST_PORT") "8101")
          manager-rest-port     (Integer/parseInt raw-manager-rest-port)
          base-uri              (str "http://" manager-ip ":" manager-rest-port "/api/v2")
          endpoint              (str "/executions")
          resource-uri          (str base-uri endpoint)
          body                  (cheshire.core/generate-string {
                                  :deployment_id           deployment-id
                                  :workflow_id             (:workflow parameters)
                                  :force                   (:force parameters)
                                  :allow_custom_parameters (:allow_custom_parameters parameters)
                                  :parameters              (:workflow_parameters parameters)})]
      (clj-http.client/post resource-uri
        {:content-type   :json
         :accept         :json
         :socket-timeout (:socket_timeout parameters)
         :conn-timeout   (:conn_timeout parameters)
         :body           body})))
