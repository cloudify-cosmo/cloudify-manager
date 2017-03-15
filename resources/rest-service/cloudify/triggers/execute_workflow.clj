(fn execute-workflow
  [ctx]
    (let [deployment-id         (:deployment_id ctx)
          parameters            (:trigger-parameters ctx)
          rest-token            "{{rest_api_token}}"
          rest-host             (or (System/getenv "REST_HOST") "127.0.0.1")
          rest-protocol         "https"
          raw-rest-port         (or (System/getenv "REST_PORT") "53333")
          rest-port             (Integer/parseInt raw-rest-port)
          tenant-id             "{{tenant_id}}"
          base-uri              (str rest-protocol "://" rest-host ":" rest-port "/api/v3")
          endpoint              (str "/executions")
          resource-uri          (str base-uri endpoint)
          body                  (cheshire.core/generate-string {
                                  :deployment_id           deployment-id
                                  :workflow_id             (:workflow parameters)
                                  :force                   (:force parameters)
                                  :allow_custom_parameters (:allow_custom_parameters parameters)
                                  :parameters              (:workflow_parameters parameters)})
          execute-api-call      (fn [] (clj-http.client/post resource-uri
                        {:content-type   :json
                         :accept         :json
                         :socket-timeout (:socket_timeout parameters)
                         :conn-timeout   (:conn_timeout parameters)
                         :headers {"API-Authentication-Token" rest-token
                                   "Tenant" tenant-id}
                         :trust-store "/etc/cloudify/ssl/cloudify_internal.p12"
                         :trust-store-type "pkcs12"
                         :trust-store-pass "cloudify"
                         :body           body}))]
    (try
        (execute-api-call)
        (catch Exception e 
             (error "Exception calling Cloudify API: " e)
             (throw e)
        )
    )
))
