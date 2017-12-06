;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Include config dir
;;

(include "/etc/riemann/conf.d/")

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Section: Global riemann configuration
;;

(logging/init {:file "/var/log/cloudify/riemann/riemann.log"})
