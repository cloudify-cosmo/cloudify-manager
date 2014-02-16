Workflow Service
================

Provides a REST api on top of `Ruote` for launching and monitoring Cloudify Cosmo workflows using the `Sinatra` framework.

## Requirements
* Ruby 2.1.0 (We test it on this version, it might also work on older ruby versions)

## Usage

### Installation
* Make sure Ruby 2.1.0 is installed.
* Make sure `bundler` is installed (gem install bundler).
* Run:

```
# Install required dependencies
bundle install

# Start the service
rackup -p <port>
```

### Logs
Logging properties can be tweaked in `log4j.properties`.
In order to enable logging per `blueprint` set a `WF_SERVICE_LOGS_PATH` environment variable pointing to a directory where log files will be saved.
Each blueprint will have its own log file - `"blueprint_name".log`.

For example:
```
export WF_SERVICE_LOGS_PATH=/var/log/cosmo/blueprints
rackup -p 8080
```

### Tests
```
rake
```

## API

### Launch A Workflow
```
POST /workflows
```
Body:
```json
{
  "radial": "Workflow to launch in Ruote's radial format",
  "fields": "Initial workflow workitem fields"
}
```
Response:
```json
{
    "id": "The workflow's Id",
    "state": "Workflow state [pending, launched, terminated, failed]",
    "created": "Time when workflow was requested to launch",
    "launched": "Actual launch time",
    "error": "On failure contains error information"
}
```
### Get Workflow State
```
GET /workflows/:id
```
Parameters:
* id - The workflow's Id to get the state for.

Response:
```json
{
    "id": "The workflow's Id",
    "state": "Workflow state [pending, launched, terminated, failed]",
    "created": "Time when workflow was requested to launch",
    "launched": "Actual launch time",
    "error": "On failure contains error information"
}
```
### Get All Workflows State
```
GET /workflows
```
Response:
```json
[
    "id": "The workflow's Id",
    "state": "Workflow state [pending, launched, terminated, failed]",
    "created": "Time when workflow was requested to launch",
    "launched": "Actual launch time",
    "error": "On failure contains error information"
]
```
