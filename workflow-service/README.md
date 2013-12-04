Workflow Service
================

Provides a REST api on top of `Ruote` for launching and monitoring Cloudify Cosmo workflows using the `Sinatra` framework.

## Requirements
* JRuby 1.7.3 (Jython requirement).

## Usage

### Installation
* Install JRuby.
* Make sure `bundler` is installed (gem install bundler).
* Run:

```
# Install required dependencies
bundle install

# Start the service
rackup -p <port>
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
