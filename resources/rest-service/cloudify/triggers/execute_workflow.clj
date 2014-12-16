(fn execute-workflow
  [ctx]
    (let [deployment-id         (:deployment-id ctx)
          parameters            (:trigger-parameters ctx)
          node-id               (:node-id ctx)
          manager-ip            (or (System/getenv "MANAGEMENT_IP") "127.0.0.1")
          raw-manager-rest-port (or (System/getenv "MANAGER_REST_PORT") "80")
          manager-rest-port     (Integer/parseInt raw-manager-rest-port)
          base-uri              (str "http://" manager-ip ":" manager-rest-port)
          endpoint              (str "/executions")
          resource-uri          (str base-uri endpoint)
          node-endpoint         (str "/node-instances/" node-id)
          node-resource-uri     (str base-uri node-endpoint)
          body                  (cheshire.core/generate-string {
                                  :deployment_id           deployment-id
                                  :workflow_id             (:workflow parameters)
                                  :force                   (:force parameters)
                                  :allow_custom_parameters (:allow_custom_parameters parameters)
                                  :parameters              (:workflow_parameters parameters)})
          get-node              (fn [] (clj-http.client/get node-resource-uri {
                                         :accept         :json
                                         :socket-timeout (:socket_timeout parameters)
                                         :conn-timeout   (:conn_timeout parameters)}))]
      (if (= (:state (cheshire.core/parse-string (:body (get-node)) true)) "started")
        (clj-http.client/post resource-uri
          {:content-type   :json
           :accept         :json
           :socket-timeout (:socket_timeout parameters)
           :conn-timeout   (:conn_timeout parameters)
           :body           body}))))
