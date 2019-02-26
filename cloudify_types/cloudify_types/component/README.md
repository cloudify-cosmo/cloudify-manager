# Cloudify Utilities: Deployment Proxy

This plugin enables a user to connect a deployment to another deployment, in effect enabling "chains" of applications or service.


### Notes

- Previously published as "Cloudify Proxy Plugin".
- A Cloudify Manager is required.
- Tested with Cloudify Manager 4.0.

## Node types:

### cloudify.datatypes.DeploymentProxy

Upload provided blueprint to manager and create deployment based on such blueprint with run install workflow.
In runtime properties will be provided outputs from deployment.

**Derived From:** `cloudify.nodes.Root`

**Properties:**

* `resource_config`:
    * `blueprint`:
        * `external_resource`: Optional, reuse already existed blueprint, by default `False`
        * `id`: blueprint name (ignored, if `deployment.external_resource` == `True`)
        * `blueprint_archive`: blueprint source (ignored, if `external_resource` == `True`)
        * `main_file_name`: blueprint main file name (ignored, if `external_resource` == `True`)
    * `deployment`:
        * `external_resource`: Optional, reuse already existed deployment, by default `False`
        * `id`: deployment name
        * `inputs`: Optional, The inputs to the deployment.
        * `outputs`: A dictionary of `{ key: value, key: value }`.
          Get `key` the deployment.
          Set `value` runtime property to the value of the output.
        * `logs`: Logs redirect settings, by default `{redirect: true}`.
           With `redirect` == `True` copy deployments events to parent deployment.
    * `reexecute`: Optional, reexecte workflows on external deployment, by default `false`
    * `executions_start_args`: Optional, params for executions
* `client`: Client configuration, if empty will be reused manager client
    * `host`: Host of Cloudify's management machine.
    * `port`: Port of REST API service on management machine.
    * `protocol`: Protocol of REST API service on management machine, defaults to http.
    * `api_version`: version of REST API service on management machine.
    * `headers`: Headers to be added to request.
    * `query_params`: Query parameters to be added to the request.
    * `cert`: Path to a copy of the server's self-signed certificate.
    * `trust_all`: if `False`, the server's certificate
                 (self-signed or not) will be verified.
    * `username`: Cloudify User username.
    * `password`: Cloudify User password.
    * `token`: Cloudify User token.
    * `tenant`: Cloudify Tenant name.
* `plugins`: Optional, list of plugins for upload.
    * `wagon_path`: Url for plugin wagon file.
    * `plugin_yaml_path`: Url for plugin yaml file.
* `secrets`: Optional, dictionary of secrets for set before run deployments.

**Workflow inputs**

* `start`:
    * `workflow_id`: workflow name for run, by default `install`.
    * `timeout`: workflow timeout.
    * `interval`: polling interval.
    * `state`: Optional, final state for workflow, by default `terminated`.
    * `pagination_offset`: Optional, pagination offset, by default `0`.
    * `pagination_size`: Optional, pagination size, by default `1000`.
* `stop`:
    * `workflow_id`: workflow name for run, by default `uninstall`.
    * `timeout`: workflow timeout.
    * `interval`: polling interval.
    * `state`: Optional, final state for workflow, by default `terminated`.
    * `pagination_offset`: Optional, pagination offset, by default `0`.
    * `pagination_size`: Optional, pagination size, by default `1000`.

**Runtime properties:**

* `blueprint`:
    * `id`: blueprint name.
    * `application_file_name`: blueprint file name.
    * `blueprint_archive`: blueprint source.
* `deployment`:
    * `id`: deployment name.
    * `outputs`: outputs from deployment
* `executions`:
    * `workflow_id`: executed workflow.
* `received_events`: list of deployment related executions with event count, option available only with log redirect option enabled.

**Examples:**
* Simple example:
```yaml
  deployment_proxy:
    type: cloudify.nodes.DeploymentProxy
    properties:
      client:
        host: 127.0.0.1
        username: admin
        password: admin
        tenant: default_tenant
      plugins:
        - wagon_path: https://github.com/cloudify-incubator/cloudify-utilities-plugin/releases/download/1.10.0/cloudify_utilities_plugin-1.9.0-py27-none-linux_x86_64-centos-Core.wgn
          plugin_yaml_path: http://www.getcloudify.org/spec/utilities-plugin/1.10.0/plugin.yaml
      resource_config:
        blueprint:
          external_resource: true
        deployment:
          external_resource: true
          id: deployment_proxy_reuse
          outputs:
            key: deployment_proxy_output
        reexecute: true
    interfaces:
      cloudify.interfaces.lifecycle:
        start:
          inputs:
            workflow_id: uninstall
        stop:
          inputs:
            workflow_id: install
```
* [Deployment proxy](examples/deployment-proxy.yaml) - save deployment outputs to runtime properties
* [Deployment reuse external blueprint](examples/deployment-proxy-reuse.yaml) - save deployment outputs to runtime properties

### cloudify.datatypes.NodeInstanceProxy

Upload provided blueprint to manager and create deployment based on such blueprint with run install workflow.
In runtime properties will be provided runtime properties from node instance.

**Derived From:** [cloudify.nodes.DeploymentProxy](#cloudifydatatypesdeploymentproxy)

**Properties:**

* `resource_config`:
    * `blueprint`:
        * `external_resource`: Optional, reuse already existed blueprint, by default `False`
        * `id`: blueprint name (ignored, if `deployment.external_resource` == `True`)
        * `blueprint_archive`: blueprint source (ignored, if `external_resource` == `True`)
        * `main_file_name`: blueprint main file name (ignored, if `external_resource` == `True`)
    * `deployment`:
        * `external_resource`: Optional, reuse already existed deployment, by default `False`
        * `id`: deployment name
        * `inputs`: Optional, The inputs to the deployment.
        * `outputs`: A dictionary of `{ key: value, key: value }`.
          Get `key` the deployment.
          Set `value` runtime property to the value of the output.
        * `logs`: Logs redirect settings, by default `{redirect: true}`.
           With `redirect` == `True` copy deployments events to parent deployment.
    * `reexecute`: Optional, reexecte workflows on external deployment, by default `false`
    * `executions_start_args`: Optional, params for executions
    * `node_instance`:
        * `node`: Optional.
            * `id`: Node id
        * `id`: Optional, instance id
* `client`: Client configuration, if empty will be reused manager client
    * `host`: Host of Cloudify's management machine.
    * `port`: Port of REST API service on management machine.
    * `protocol`: Protocol of REST API service on management machine, defaults to http.
    * `api_version`: version of REST API service on management machine.
    * `headers`: Headers to be added to request.
    * `query_params`: Query parameters to be added to the request.
    * `cert`: Path to a copy of the server's self-signed certificate.
    * `trust_all`: if `False`, the server's certificate
                 (self-signed or not) will be verified.
    * `username`: Cloudify User username.
    * `password`: Cloudify User password.
    * `token`: Cloudify User token.
    * `tenant`: Cloudify Tenant name.

**Runtime properties:**

* `blueprint`:
    * `id`: blueprint name.
    * `application_file_name`: blueprint file name.
    * `blueprint_archive`: blueprint source.
* `deployment`:
    * `id`: deployment name.
* `executions`:
    * `workflow_id`: executed workflow.
* `received_events`: list of deployment related executions with event count, option available only with log redirect option enabled.
* `NodeInstanceProxy`: runtime properties from slave deployment instance.

**Workflow inputs**

* `start`:
    * `workflow_id`: workflow name for run, by default `install`.
* `stop`:
    * `workflow_id`: workflow name for run, by default `uninstall`.

**Examples:**

* [Node instance proxy](examples/node-instance-proxy.yaml) - save instance properties to runtime properties

## Examples:

- [Test Example](#test-example-instructions)
- [Deployment proxy](examples/deployment-proxy.yaml) - save deployment outputs to runtime properties
- [Deployment reuse external blueprint](examples/deployment-proxy-reuse.yaml) - save deployment outputs to runtime properties
- [Node instance proxy](examples/node-instance-proxy.yaml) - save instance properties to runtime properties

```shell
$ cfy install cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-proxy.yaml -b one -d one
Uploading blueprint cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-proxy.yaml...
 deployment-proxy.... |################################################| 100.0%
Blueprint uploaded. The blueprint's id is one
Creating new deployment from blueprint one...
Deployment created. The deployment's id is one
Executing workflow install on deployment one [timeout=900 seconds]
Deployment environment creation is in progress...
2017-06-20 15:02:32.177  CFY <one> Starting 'create_deployment_environment' workflow execution
2017-06-20 15:02:33.086  LOG <one> [,] INFO: Installing plugin: cfy_util
2017-06-20 15:02:33.388  CFY <one> Installing deployment plugins
2017-06-20 15:02:33.388  CFY <one> [,] Sending task 'cloudify_agent.operations.install_plugins'
2017-06-20 15:02:33.388  CFY <one> [,] Task started 'cloudify_agent.operations.install_plugins'
2017-06-20 15:02:34.152  LOG <one> [,] INFO: Installing plugin from source
2017-06-20 15:02:38.159  LOG <one> [,] INFO: Installing plugin: configuration
2017-06-20 15:02:38.159  LOG <one> [,] INFO: Installing plugin from source
2017-06-20 15:02:42.205  CFY <one> [,] Task succeeded 'cloudify_agent.operations.install_plugins'
2017-06-20 15:02:43.220  CFY <one> 'create_deployment_environment' workflow execution succeeded
2017-06-20 15:02:43.220  CFY <one> Creating deployment work directory
2017-06-20 15:02:43.220  CFY <one> Skipping starting deployment policy engine core - no policies defined
2017-06-20 15:02:48.543  CFY <one> Starting 'install' workflow execution
2017-06-20 15:02:49.773  CFY <one> [deployment_proxy_rjxlf0] Creating node
2017-06-20 15:02:49.773  CFY <one> [deployment_proxy_rjxlf0.create] Sending task 'cloudify_deployment_proxy.tasks.upload_blueprint'
2017-06-20 15:02:50.395  CFY <one> [deployment_proxy_rjxlf0.create] Task started 'cloudify_deployment_proxy.tasks.upload_blueprint'
2017-06-20 15:02:53.423  CFY <one> [deployment_proxy_rjxlf0.create] Task succeeded 'cloudify_deployment_proxy.tasks.upload_blueprint ("{u'main_file_name': u'blueprint.yaml', u'description': None, u'tenant_name': u'default_tenant', u'created_at':...")'
2017-06-20 15:02:54.397  CFY <one> [deployment_proxy_rjxlf0] Configuring node
2017-06-20 15:02:54.397  CFY <one> [deployment_proxy_rjxlf0.configure] Sending task 'cloudify_deployment_proxy.tasks.create_deployment'
2017-06-20 15:02:54.397  CFY <one> [deployment_proxy_rjxlf0.configure] Task started 'cloudify_deployment_proxy.tasks.create_deployment'
2017-06-20 15:02:54.801  LOG <one> [deployment_proxy_rjxlf0.configure] INFO: Create deployment deployment_proxy.
2017-06-20 15:03:05.341  LOG <one> [deployment_proxy_rjxlf0.configure] INFO: 2017-06-20T15:02:55.953Z Starting 'create_deployment_environment' workflow execution
2017-06-20 15:03:05.504  CFY <one> [deployment_proxy_rjxlf0.configure] Task succeeded 'cloudify_deployment_proxy.tasks.create_deployment ('True')'
2017-06-20 15:03:06.186  LOG <one> [deployment_proxy_rjxlf0.configure] INFO: 2017-06-20T15:02:57.032Z 'create_deployment_environment' workflow execution succeeded
2017-06-20 15:03:06.186  LOG <one> [deployment_proxy_rjxlf0.configure] INFO: 2017-06-20T15:02:57.032Z Creating deployment work directory
2017-06-20 15:03:06.186  LOG <one> [deployment_proxy_rjxlf0.configure] INFO: 2017-06-20T15:02:57.032Z Skipping starting deployment policy engine core - no policies defined
2017-06-20 15:03:06.404  CFY <one> [deployment_proxy_rjxlf0.start] Sending task 'cloudify_deployment_proxy.tasks.execute_start'
2017-06-20 15:03:06.404  CFY <one> [deployment_proxy_rjxlf0] Starting node
2017-06-20 15:03:06.404  CFY <one> [deployment_proxy_rjxlf0.start] Task started 'cloudify_deployment_proxy.tasks.execute_start'
2017-06-20 15:03:17.119  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:07.730Z Starting 'install' workflow execution
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:10.407Z [not_a_node_template_xn6tt0.configure] Sending task 'script_runner.tasks.run'
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:10.407Z [not_a_node_template_xn6tt0.configure] Task started 'script_runner.tasks.run'
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:10.401Z [not_a_node_template_xn6tt0.configure] Downloaded configure.sh to /tmp/401AL/configure.sh
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:09.265Z [not_a_node_template_xn6tt0] Creating node
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:11.193Z [not_a_node_template_xn6tt0.configure] Executing: /tmp/401AL/configure.sh
2017-06-20 15:03:17.196  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:09.265Z [not_a_node_template_xn6tt0] Configuring node
2017-06-20 15:03:17.430  CFY <one> [deployment_proxy_rjxlf0.start] Task succeeded 'cloudify_deployment_proxy.tasks.execute_start ('True')'
2017-06-20 15:03:18.200  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:11.408Z [not_a_node_template_xn6tt0] Starting node
2017-06-20 15:03:18.200  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:11.193Z [not_a_node_template_xn6tt0.configure] Execution done (return_code=0): /tmp/401AL/configure.sh
2017-06-20 15:03:18.200  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:12.410Z 'install' workflow execution succeeded
2017-06-20 15:03:18.200  LOG <one> [deployment_proxy_rjxlf0.start] INFO: 2017-06-20T15:03:11.408Z [not_a_node_template_xn6tt0.configure] Task succeeded 'script_runner.tasks.run'
2017-06-20 15:03:18.414  CFY <one> 'install' workflow execution succeeded
Finished executing workflow install on deployment one
* Run 'cfy events list -e 27ce2cb8-cfc4-4356-a7b4-7c776b9be680' to retrieve the execution's events/logs
```

```shell
$ cfy uninstall one
Executing workflow uninstall on deployment one [timeout=900 seconds]
2017-06-20 15:03:57.601  CFY <one> Starting 'uninstall' workflow execution
2017-06-20 15:03:58.423  CFY <one> [deployment_proxy_rjxlf0] Stopping node
2017-06-20 15:03:59.425  CFY <one> [deployment_proxy_rjxlf0.stop] Sending task 'cloudify_deployment_proxy.tasks.execute_start'
2017-06-20 15:03:59.425  CFY <one> [deployment_proxy_rjxlf0.stop] Task started 'cloudify_deployment_proxy.tasks.execute_start'
2017-06-20 15:04:10.042  LOG <one> [deployment_proxy_rjxlf0.stop] INFO: 2017-06-20T15:04:00.656Z Starting 'uninstall' workflow execution
2017-06-20 15:04:10.207  CFY <one> [deployment_proxy_rjxlf0.stop] Task succeeded 'cloudify_deployment_proxy.tasks.execute_start ('True')'
2017-06-20 15:04:10.215  LOG <one> [deployment_proxy_rjxlf0.stop] INFO: 2017-06-20T15:04:02.264Z [not_a_node_template_xn6tt0] Stopping node
2017-06-20 15:04:10.215  LOG <one> [deployment_proxy_rjxlf0.stop] INFO: 2017-06-20T15:04:03.429Z 'uninstall' workflow execution succeeded
2017-06-20 15:04:10.215  LOG <one> [deployment_proxy_rjxlf0.stop] INFO: 2017-06-20T15:04:02.264Z [not_a_node_template_xn6tt0] Deleting node
2017-06-20 15:04:11.435  CFY <one> [deployment_proxy_rjxlf0.delete] Task started 'cloudify_deployment_proxy.tasks.delete_deployment'
2017-06-20 15:04:11.435  CFY <one> [deployment_proxy_rjxlf0.delete] Sending task 'cloudify_deployment_proxy.tasks.delete_deployment'
2017-06-20 15:04:11.435  CFY <one> [deployment_proxy_rjxlf0] Deleting node
2017-06-20 15:04:11.611  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Wait for stop deployment related executions.
2017-06-20 15:04:12.220  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Wait for deployment delete.
2017-06-20 15:04:12.220  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Delete deployment deployment_proxy
2017-06-20 15:04:12.220  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Little wait internal cleanup services.
2017-06-20 15:04:22.101  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Wait for stop all system workflows.
2017-06-20 15:04:22.226  LOG <one> [deployment_proxy_rjxlf0.delete] INFO: Delete blueprint deployment_proxy.
2017-06-20 15:04:22.318  CFY <one> [deployment_proxy_rjxlf0.delete] Task succeeded 'cloudify_deployment_proxy.tasks.delete_deployment ('True')'
2017-06-20 15:04:23.440  CFY <one> 'uninstall' workflow execution succeeded
Finished executing workflow uninstall on deployment one
* Run 'cfy events list -e 241c15dd-2f4f-489c-b825-695d17dd0240' to retrieve the execution's events/logs
Deleting deployment one...
Deployment deleted
Deleting blueprint one...
Blueprint deleted
```


### Check external resource

# upload blueprint

```shell
$ cfy install cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-proxy.yaml -b one -d one
```

# reuse blueprint

```shell
$ cfy install cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-proxy-reuse.yaml -b two -d two
```


# reuse deployment

```shell
$ cfy install cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-proxy-custom-workflow.yaml -b three -d three
````

# reuse only outputs from one

```shell
cfy install cloudify-utilities-plugin/cloudify_deployment_proxy/examples/deployment-without-workflow.yaml -b four -d four
````

# delete all

```shell
$ cfy uninstall four
$ cfy uninstall three
$ cfy uninstall two
$ cfy uninstall one
```
