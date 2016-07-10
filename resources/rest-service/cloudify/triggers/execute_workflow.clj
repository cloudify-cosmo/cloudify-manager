(fn execute-workflow
  [ctx]
    (let [deployment-id         (:deployment_id ctx)
          parameters            (:trigger-parameters ctx)
          rest-host             (or (System/getenv "REST_HOST") "127.0.0.1")
          rest-protocol         (or (System/getenv "REST_PROTOCOL") "http")
          raw-rest-port         (or (System/getenv "REST_PORT") "80")
          rest-port             (Integer/parseInt raw-rest-port)
          verify-ssl-cert       false
          base-uri              (str rest-protocol "://" rest-host ":" rest-port "/api/v2")
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
         :insecure?      (not verify-ssl-cert)
         :body           body})))
