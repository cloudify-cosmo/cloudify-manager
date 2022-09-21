BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 333998bc1627

CREATE TABLE groups (
    id SERIAL NOT NULL, 
    name TEXT NOT NULL, 
    ldap_dn TEXT, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_groups_ldap_dn ON groups (ldap_dn);

CREATE UNIQUE INDEX ix_groups_name ON groups (name);

CREATE TABLE provider_context (
    id TEXT NOT NULL, 
    name TEXT NOT NULL, 
    context BYTEA NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE roles (
    id SERIAL NOT NULL, 
    name TEXT NOT NULL, 
    description TEXT, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_roles_name ON roles (name);

CREATE TABLE tenants (
    id SERIAL NOT NULL, 
    name TEXT, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_tenants_name ON tenants (name);

CREATE TABLE users (
    id SERIAL NOT NULL, 
    username VARCHAR(255), 
    active BOOLEAN, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    email VARCHAR(255), 
    first_name VARCHAR(255), 
    last_login_at TIMESTAMP WITHOUT TIME ZONE, 
    last_name VARCHAR(255), 
    password VARCHAR(255), 
    api_token_key VARCHAR(100), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_username ON users (username);

CREATE TABLE blueprints (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    main_file_name TEXT NOT NULL, 
    plan BYTEA NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    description TEXT, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_blueprints_created_at ON blueprints (created_at);

CREATE INDEX ix_blueprints_id ON blueprints (id);

CREATE TABLE groups_tenants (
    group_id INTEGER, 
    tenant_id INTEGER, 
    FOREIGN KEY(group_id) REFERENCES groups (id), 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);

CREATE TABLE plugins (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    archive_name TEXT NOT NULL, 
    distribution TEXT, 
    distribution_release TEXT, 
    distribution_version TEXT, 
    excluded_wheels BYTEA, 
    package_name TEXT NOT NULL, 
    package_source TEXT, 
    package_version TEXT, 
    supported_platform BYTEA, 
    supported_py_versions BYTEA, 
    uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    wheels BYTEA NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_plugins_archive_name ON plugins (archive_name);

CREATE INDEX ix_plugins_id ON plugins (id);

CREATE INDEX ix_plugins_package_name ON plugins (package_name);

CREATE INDEX ix_plugins_uploaded_at ON plugins (uploaded_at);

CREATE TABLE secrets (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    value TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_secrets_created_at ON secrets (created_at);

CREATE INDEX ix_secrets_id ON secrets (id);

CREATE TYPE snapshot_status AS ENUM ('created', 'failed', 'creating', 'uploaded');

CREATE TABLE snapshots (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    status snapshot_status, 
    error TEXT, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_snapshots_created_at ON snapshots (created_at);

CREATE INDEX ix_snapshots_id ON snapshots (id);

CREATE TABLE users_groups (
    user_id INTEGER, 
    group_id INTEGER, 
    FOREIGN KEY(group_id) REFERENCES groups (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE users_roles (
    user_id INTEGER, 
    role_id INTEGER, 
    FOREIGN KEY(role_id) REFERENCES roles (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE users_tenants (
    user_id INTEGER, 
    tenant_id INTEGER, 
    FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE deployments (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    description TEXT, 
    inputs BYTEA, 
    groups BYTEA, 
    permalink TEXT, 
    policy_triggers BYTEA, 
    policy_types BYTEA, 
    outputs BYTEA, 
    scaling_groups BYTEA, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    workflows BYTEA, 
    _blueprint_fk INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE CASCADE, 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_deployments_created_at ON deployments (created_at);

CREATE INDEX ix_deployments_id ON deployments (id);

CREATE TABLE owners_blueprints_users (
    blueprint_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(blueprint_id) REFERENCES blueprints (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE owners_plugins_users (
    plugin_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(plugin_id) REFERENCES plugins (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE owners_secrets_users (
    secret_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(secret_id) REFERENCES secrets (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE owners_snapshots_users (
    snapshot_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(snapshot_id) REFERENCES snapshots (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_blueprints_users (
    blueprint_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(blueprint_id) REFERENCES blueprints (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_plugins_users (
    plugin_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(plugin_id) REFERENCES plugins (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_secrets_users (
    secret_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(secret_id) REFERENCES secrets (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_snapshots_users (
    snapshot_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(snapshot_id) REFERENCES snapshots (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TYPE deployment_modification_status AS ENUM ('started', 'finished', 'rolledback');

CREATE TABLE deployment_modifications (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    context BYTEA, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    ended_at TIMESTAMP WITHOUT TIME ZONE, 
    modified_nodes BYTEA, 
    node_instances BYTEA, 
    status deployment_modification_status, 
    _deployment_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_deployment_modifications_created_at ON deployment_modifications (created_at);

CREATE INDEX ix_deployment_modifications_ended_at ON deployment_modifications (ended_at);

CREATE INDEX ix_deployment_modifications_id ON deployment_modifications (id);

CREATE TYPE execution_status AS ENUM ('terminated', 'failed', 'cancelled', 'pending', 'started', 'cancelling', 'force_cancelling');

CREATE TABLE executions (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    error TEXT, 
    is_system_workflow BOOLEAN NOT NULL, 
    parameters BYTEA, 
    status execution_status, 
    workflow_id TEXT NOT NULL, 
    _deployment_fk INTEGER, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX ix_executions_created_at ON executions (created_at);

CREATE INDEX ix_executions_id ON executions (id);

CREATE TABLE nodes (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    deploy_number_of_instances INTEGER NOT NULL, 
    host_id TEXT, 
    max_number_of_instances INTEGER NOT NULL, 
    min_number_of_instances INTEGER NOT NULL, 
    number_of_instances INTEGER NOT NULL, 
    planned_number_of_instances INTEGER NOT NULL, 
    plugins BYTEA, 
    plugins_to_install BYTEA, 
    properties BYTEA, 
    relationships BYTEA, 
    operations BYTEA, 
    type TEXT NOT NULL, 
    type_hierarchy BYTEA, 
    _deployment_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_nodes_id ON nodes (id);

CREATE INDEX ix_nodes_type ON nodes (type);

CREATE TABLE owners_deployments_users (
    deployment_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(deployment_id) REFERENCES deployments (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_deployments_users (
    deployment_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(deployment_id) REFERENCES deployments (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE deployment_updates (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    deployment_plan BYTEA, 
    deployment_update_node_instances BYTEA, 
    deployment_update_deployment BYTEA, 
    deployment_update_nodes BYTEA, 
    modified_entity_ids BYTEA, 
    state TEXT, 
    _execution_fk INTEGER, 
    _deployment_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_deployment_updates_created_at ON deployment_updates (created_at);

CREATE INDEX ix_deployment_updates_id ON deployment_updates (id);

CREATE TABLE events (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    message TEXT, 
    message_code TEXT, 
    event_type TEXT, 
    operation TEXT, 
    node_id TEXT, 
    _execution_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_events_id ON events (id);

CREATE INDEX ix_events_timestamp ON events (timestamp);

CREATE TABLE logs (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    message TEXT, 
    message_code TEXT, 
    logger TEXT, 
    level TEXT, 
    operation TEXT, 
    node_id TEXT, 
    _execution_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_logs_id ON logs (id);

CREATE INDEX ix_logs_timestamp ON logs (timestamp);

CREATE TABLE node_instances (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    host_id TEXT, 
    relationships BYTEA, 
    runtime_properties BYTEA, 
    scaling_groups BYTEA, 
    state TEXT NOT NULL, 
    version INTEGER, 
    _node_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_node_fk) REFERENCES nodes (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_node_instances_id ON node_instances (id);

CREATE TABLE owners_executions_users (
    execution_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(execution_id) REFERENCES executions (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE viewers_executions_users (
    execution_id INTEGER, 
    user_id INTEGER, 
    FOREIGN KEY(execution_id) REFERENCES executions (_storage_id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TYPE action_type AS ENUM ('add', 'remove', 'modify');

CREATE TYPE entity_type AS ENUM ('node', 'relationship', 'property', 'operation', 'workflow', 'output', 'description', 'group', 'policy_type', 'policy_trigger', 'plugin');

CREATE TABLE deployment_update_steps (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    action action_type, 
    entity_id TEXT NOT NULL, 
    entity_type entity_type, 
    _deployment_update_fk INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_deployment_update_fk) REFERENCES deployment_updates (_storage_id) ON DELETE CASCADE
);

CREATE INDEX ix_deployment_update_steps_id ON deployment_update_steps (id);

INSERT INTO alembic_version (version_num) VALUES ('333998bc1627') RETURNING alembic_version.version_num;

-- Running upgrade 333998bc1627 -> 9aa6f74c9653

DROP TABLE owners_secrets_users;

DROP TABLE owners_snapshots_users;

DROP TABLE viewers_executions_users;

DROP TABLE viewers_snapshots_users;

DROP TABLE viewers_plugins_users;

DROP TABLE viewers_blueprints_users;

DROP TABLE owners_plugins_users;

DROP TABLE viewers_deployments_users;

DROP TABLE owners_blueprints_users;

DROP TABLE viewers_secrets_users;

DROP TABLE owners_executions_users;

DROP TABLE owners_deployments_users;

ALTER TABLE blueprints ADD COLUMN private_resource BOOLEAN;

ALTER TABLE deployment_modifications ADD COLUMN _creator_id INTEGER NOT NULL;

ALTER TABLE deployment_modifications ADD COLUMN _tenant_id INTEGER NOT NULL;

ALTER TABLE deployment_modifications ADD COLUMN private_resource BOOLEAN;

ALTER TABLE deployment_modifications ADD CONSTRAINT deployment_modifications__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE deployment_modifications ADD CONSTRAINT deployment_modifications__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE deployment_update_steps ADD COLUMN _creator_id INTEGER NOT NULL;

ALTER TABLE deployment_update_steps ADD COLUMN _tenant_id INTEGER NOT NULL;

ALTER TABLE deployment_update_steps ADD COLUMN private_resource BOOLEAN;

ALTER TABLE deployment_update_steps ADD CONSTRAINT deployment_update_steps__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE deployment_update_steps ADD CONSTRAINT deployment_update_steps__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE deployment_updates ADD COLUMN _creator_id INTEGER NOT NULL;

ALTER TABLE deployment_updates ADD COLUMN _tenant_id INTEGER NOT NULL;

ALTER TABLE deployment_updates ADD COLUMN private_resource BOOLEAN;

ALTER TABLE deployment_updates ADD CONSTRAINT deployment_updates__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE deployment_updates ADD CONSTRAINT deployment_updates__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE deployments ADD COLUMN _tenant_id INTEGER;

UPDATE deployments SET _tenant_id = blueprints._tenant_id FROM blueprints WHERE deployments._blueprint_fk = blueprints._storage_id;

ALTER TABLE deployments ALTER COLUMN _tenant_id SET NOT NULL;

ALTER TABLE deployments ADD COLUMN private_resource BOOLEAN;

ALTER TABLE deployments ADD CONSTRAINT deployments__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE events ADD COLUMN _creator_id INTEGER;

ALTER TABLE events ADD COLUMN _tenant_id INTEGER;

ALTER TABLE events ADD COLUMN reported_timestamp TIMESTAMP WITHOUT TIME ZONE;

UPDATE events SET _creator_id = executions._creator_id, _tenant_id = executions._tenant_id, reported_timestamp = timestamp FROM executions WHERE events._execution_fk = executions._storage_id;

ALTER TABLE events ALTER COLUMN _creator_id SET NOT NULL;

ALTER TABLE events ALTER COLUMN _tenant_id SET NOT NULL;

ALTER TABLE events ALTER COLUMN reported_timestamp SET NOT NULL;

ALTER TABLE events ALTER COLUMN timestamp SET NOT NULL;

ALTER TABLE events ALTER COLUMN timestamp SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE events ADD COLUMN error_causes TEXT;

ALTER TABLE events ADD COLUMN private_resource BOOLEAN;

ALTER TABLE events ADD CONSTRAINT events__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE events ADD CONSTRAINT events__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE executions ADD COLUMN private_resource BOOLEAN;

ALTER TABLE logs ADD COLUMN _creator_id INTEGER;

ALTER TABLE logs ADD COLUMN _tenant_id INTEGER;

ALTER TABLE logs ADD COLUMN reported_timestamp TIMESTAMP WITHOUT TIME ZONE;

UPDATE logs SET _creator_id = executions._creator_id, _tenant_id = executions._tenant_id, reported_timestamp = timestamp FROM executions WHERE logs._execution_fk = executions._storage_id;

ALTER TABLE logs ALTER COLUMN _creator_id SET NOT NULL;

ALTER TABLE logs ALTER COLUMN _tenant_id SET NOT NULL;

ALTER TABLE logs ALTER COLUMN reported_timestamp SET NOT NULL;

ALTER TABLE logs ALTER COLUMN timestamp SET NOT NULL;

ALTER TABLE logs ALTER COLUMN timestamp SET DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE logs ADD COLUMN private_resource BOOLEAN;

ALTER TABLE logs ADD CONSTRAINT logs__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE logs ADD CONSTRAINT logs__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE nodes ADD COLUMN _creator_id INTEGER;

ALTER TABLE nodes ADD COLUMN _tenant_id INTEGER;

UPDATE nodes SET _creator_id = deployments._creator_id, _tenant_id = deployments._tenant_id FROM deployments WHERE nodes._deployment_fk = deployments._storage_id;

ALTER TABLE nodes ALTER COLUMN _creator_id SET NOT NULL;

ALTER TABLE nodes ALTER COLUMN _tenant_id SET NOT NULL;

ALTER TABLE nodes ADD COLUMN private_resource BOOLEAN;

ALTER TABLE nodes ADD CONSTRAINT nodes__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE nodes ADD CONSTRAINT nodes__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE node_instances ADD COLUMN _creator_id INTEGER;

ALTER TABLE node_instances ADD COLUMN _tenant_id INTEGER;

UPDATE node_instances SET _creator_id = nodes._creator_id, _tenant_id = nodes._tenant_id FROM nodes WHERE node_instances._node_fk = nodes._storage_id;

ALTER TABLE node_instances ALTER COLUMN _creator_id SET NOT NULL;

ALTER TABLE node_instances ALTER COLUMN _tenant_id SET NOT NULL;

ALTER TABLE node_instances ADD COLUMN private_resource BOOLEAN;

ALTER TABLE node_instances ADD CONSTRAINT node_instances__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE node_instances ADD CONSTRAINT node_instances__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE plugins ADD COLUMN private_resource BOOLEAN;

ALTER TABLE secrets ADD COLUMN private_resource BOOLEAN;

ALTER TABLE snapshots ADD COLUMN private_resource BOOLEAN;

UPDATE alembic_version SET version_num='9aa6f74c9653' WHERE alembic_version.version_num = '333998bc1627';

-- Running upgrade 9aa6f74c9653 -> 730403566523

CREATE INDEX blueprints_created_at_idx ON blueprints (created_at);

CREATE INDEX blueprints_id_idx ON blueprints (id);

CREATE INDEX deployment_modifications_created_at_idx ON deployment_modifications (created_at);

CREATE INDEX deployment_modifications_ended_at_idx ON deployment_modifications (ended_at);

CREATE INDEX deployment_modifications_id_idx ON deployment_modifications (id);

CREATE INDEX deployment_update_steps_id_idx ON deployment_update_steps (id);

CREATE INDEX deployment_updates_created_at_idx ON deployment_updates (created_at);

CREATE INDEX deployment_updates_id_idx ON deployment_updates (id);

CREATE INDEX deployments_created_at_idx ON deployments (created_at);

CREATE INDEX deployments_id_idx ON deployments (id);

CREATE INDEX events_id_idx ON events (id);

CREATE INDEX events_timestamp_idx ON events (timestamp);

DROP INDEX ix_events_timestamp;

CREATE INDEX executions_created_at_idx ON executions (created_at);

CREATE INDEX executions_id_idx ON executions (id);

CREATE UNIQUE INDEX groups_ldap_dn_idx ON groups (ldap_dn);

CREATE UNIQUE INDEX groups_name_idx ON groups (name);

CREATE INDEX logs_id_idx ON logs (id);

CREATE INDEX logs_timestamp_idx ON logs (timestamp);

DROP INDEX ix_logs_timestamp;

CREATE INDEX node_instances_id_idx ON node_instances (id);

CREATE INDEX nodes_id_idx ON nodes (id);

CREATE INDEX nodes_type_idx ON nodes (type);

CREATE INDEX plugins_archive_name_idx ON plugins (archive_name);

CREATE INDEX plugins_id_idx ON plugins (id);

CREATE INDEX plugins_package_name_idx ON plugins (package_name);

CREATE INDEX plugins_uploaded_at_idx ON plugins (uploaded_at);

CREATE UNIQUE INDEX roles_name_idx ON roles (name);

CREATE INDEX secrets_created_at_idx ON secrets (created_at);

CREATE INDEX secrets_id_idx ON secrets (id);

CREATE INDEX snapshots_created_at_idx ON snapshots (created_at);

CREATE INDEX snapshots_id_idx ON snapshots (id);

ALTER TABLE tenants ADD COLUMN rabbitmq_password TEXT;

ALTER TABLE tenants ADD COLUMN rabbitmq_username TEXT;

ALTER TABLE tenants ADD COLUMN rabbitmq_vhost TEXT;

CREATE UNIQUE INDEX tenants_name_idx ON tenants (name);

CREATE UNIQUE INDEX users_username_idx ON users (username);

UPDATE alembic_version SET version_num='730403566523' WHERE alembic_version.version_num = '9aa6f74c9653';

-- Running upgrade 730403566523 -> 3496c876cd1a

ALTER TABLE events ALTER COLUMN timestamp SET NOT NULL;

ALTER TABLE events ALTER COLUMN timestamp DROP DEFAULT;

ALTER TABLE logs ALTER COLUMN timestamp SET NOT NULL;

ALTER TABLE logs ALTER COLUMN timestamp DROP DEFAULT;

UPDATE alembic_version SET version_num='3496c876cd1a' WHERE alembic_version.version_num = '730403566523';

-- Running upgrade 3496c876cd1a -> 4dfd8797fdfa

CREATE TYPE resource_availability AS ENUM ('private', 'tenant', 'global');

ALTER TABLE blueprints ADD COLUMN resource_availability resource_availability;

UPDATE blueprints
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE plugins ADD COLUMN resource_availability resource_availability;

UPDATE plugins
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE secrets ADD COLUMN resource_availability resource_availability;

UPDATE secrets
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE snapshots ADD COLUMN resource_availability resource_availability;

UPDATE snapshots
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE events ADD COLUMN resource_availability resource_availability;

UPDATE events
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE executions ADD COLUMN resource_availability resource_availability;

UPDATE executions
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE logs ADD COLUMN resource_availability resource_availability;

UPDATE logs
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE nodes ADD COLUMN resource_availability resource_availability;

UPDATE nodes
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE node_instances ADD COLUMN resource_availability resource_availability;

UPDATE node_instances
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE deployments ADD COLUMN resource_availability resource_availability;

UPDATE deployments
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE deployment_modifications ADD COLUMN resource_availability resource_availability;

UPDATE deployment_modifications
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE deployment_updates ADD COLUMN resource_availability resource_availability;

UPDATE deployment_updates
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

ALTER TABLE deployment_update_steps ADD COLUMN resource_availability resource_availability;

UPDATE deployment_update_steps
                      SET resource_availability = CAST (CASE
                          WHEN (private_resource is true) THEN 'private'
                          WHEN (private_resource is false) THEN 'tenant'
                      END AS resource_availability);;

UPDATE alembic_version SET version_num='4dfd8797fdfa' WHERE alembic_version.version_num = '3496c876cd1a';

-- Running upgrade 4dfd8797fdfa -> 406821843b55

ALTER TABLE users_tenants ADD COLUMN role_id INTEGER;

ALTER TABLE users_tenants ADD CONSTRAINT users_tenants_role_id_fkey FOREIGN KEY(role_id) REFERENCES roles (id);

ALTER TABLE users_tenants ADD CONSTRAINT users_tenants_pkey PRIMARY KEY (user_id, tenant_id);

UPDATE users_tenants SET role_id=(SELECT roles.id 
FROM roles 
WHERE roles.name = 'user');

ALTER TABLE users_tenants ALTER COLUMN role_id SET NOT NULL;

UPDATE users_roles SET role_id=(SELECT roles.id 
FROM roles 
WHERE roles.name = 'default') WHERE users_roles.role_id = 2;

UPDATE users_roles SET role_id=(SELECT roles.id 
FROM roles 
WHERE roles.name = 'sys_admin') WHERE users_roles.role_id = 1;

UPDATE alembic_version SET version_num='406821843b55' WHERE alembic_version.version_num = '4dfd8797fdfa';

-- Running upgrade 406821843b55 -> 7aae863786af

ALTER TABLE groups_tenants ADD COLUMN role_id INTEGER;

ALTER TABLE groups_tenants ADD CONSTRAINT groups_tenants_role_id_fkey FOREIGN KEY(role_id) REFERENCES roles (id);

ALTER TABLE groups_tenants ADD CONSTRAINT groups_tenants_pkey PRIMARY KEY (group_id, tenant_id);

UPDATE groups_tenants SET role_id=(SELECT roles.id 
FROM roles 
WHERE roles.name = 'user');

ALTER TABLE groups_tenants ALTER COLUMN role_id SET NOT NULL;

UPDATE alembic_version SET version_num='7aae863786af' WHERE alembic_version.version_num = '406821843b55';

-- Running upgrade 7aae863786af -> f1dab814a4a0

ALTER TABLE node_instances ALTER COLUMN version SET NOT NULL;

UPDATE alembic_version SET version_num='f1dab814a4a0' WHERE alembic_version.version_num = '7aae863786af';

-- Running upgrade f1dab814a4a0 -> 784a82cec07a

CREATE TABLE groups_roles (
    group_id INTEGER, 
    role_id INTEGER, 
    FOREIGN KEY(role_id) REFERENCES roles (id), 
    FOREIGN KEY(group_id) REFERENCES groups (id)
);

INSERT INTO groups_roles SELECT id, 6 FROM groups;

UPDATE alembic_version SET version_num='784a82cec07a' WHERE alembic_version.version_num = 'f1dab814a4a0';

-- Running upgrade 784a82cec07a -> 3483e421713d

CREATE TYPE visibility_states AS ENUM ('private', 'tenant', 'global');

ALTER TABLE blueprints ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE blueprints RENAME resource_availability TO visibility;

ALTER TABLE plugins ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE plugins RENAME resource_availability TO visibility;

ALTER TABLE secrets ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE secrets RENAME resource_availability TO visibility;

ALTER TABLE snapshots ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE snapshots RENAME resource_availability TO visibility;

ALTER TABLE events ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE events RENAME resource_availability TO visibility;

ALTER TABLE executions ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE executions RENAME resource_availability TO visibility;

ALTER TABLE logs ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE logs RENAME resource_availability TO visibility;

ALTER TABLE nodes ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE nodes RENAME resource_availability TO visibility;

ALTER TABLE node_instances ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE node_instances RENAME resource_availability TO visibility;

ALTER TABLE deployments ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE deployments RENAME resource_availability TO visibility;

ALTER TABLE deployment_modifications ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE deployment_modifications RENAME resource_availability TO visibility;

ALTER TABLE deployment_updates ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE deployment_updates RENAME resource_availability TO visibility;

ALTER TABLE deployment_update_steps ALTER COLUMN resource_availability TYPE visibility_states USING resource_availability::text::visibility_states;

ALTER TABLE deployment_update_steps RENAME resource_availability TO visibility;

DROP TYPE resource_availability;;

UPDATE alembic_version SET version_num='3483e421713d' WHERE alembic_version.version_num = '784a82cec07a';

-- Running upgrade 3483e421713d -> c7652b2a97a4

ALTER TABLE secrets ADD COLUMN is_hidden_value BOOLEAN DEFAULT 'f' NOT NULL;

ALTER TABLE deployment_updates ADD COLUMN _old_blueprint_fk INTEGER;

ALTER TABLE deployment_updates ADD COLUMN _new_blueprint_fk INTEGER;

ALTER TABLE deployment_updates ADD COLUMN old_inputs BYTEA;

ALTER TABLE deployment_updates ADD COLUMN new_inputs BYTEA;

ALTER TABLE users ADD COLUMN last_failed_login_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE users ADD COLUMN failed_logins_counter INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE executions ADD COLUMN ended_at TIMESTAMP WITHOUT TIME ZONE;

COMMIT;

alter type execution_status add value 'kill_cancelling';

BEGIN;

UPDATE alembic_version SET version_num='c7652b2a97a4' WHERE alembic_version.version_num = '3483e421713d';

-- Running upgrade c7652b2a97a4 -> a6d00b128933

ALTER TABLE executions ADD COLUMN started_at TIMESTAMP WITHOUT TIME ZONE;

COMMIT;

alter type execution_status add value 'queued';

BEGIN;

CREATE INDEX events__execution_fk_idx ON events (_execution_fk);

CREATE INDEX logs__execution_fk_idx ON logs (_execution_fk);

ALTER TABLE groups_tenants DROP CONSTRAINT groups_tenants_group_id_fkey;

ALTER TABLE groups_tenants DROP CONSTRAINT groups_tenants_tenant_id_fkey;

ALTER TABLE groups_tenants DROP CONSTRAINT groups_tenants_role_id_fkey;

ALTER TABLE groups_tenants ADD CONSTRAINT groups_tenants_tenant_id_fkey FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE groups_tenants ADD CONSTRAINT groups_tenants_group_id_fkey FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE;

ALTER TABLE groups_tenants ADD CONSTRAINT groups_tenants_role_id_fkey FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE;

ALTER TABLE users_tenants DROP CONSTRAINT users_tenants_user_id_fkey;

ALTER TABLE users_tenants DROP CONSTRAINT users_tenants_tenant_id_fkey;

ALTER TABLE users_tenants DROP CONSTRAINT users_tenants_role_id_fkey;

ALTER TABLE users_tenants ADD CONSTRAINT users_tenants_tenant_id_fkey FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE CASCADE;

ALTER TABLE users_tenants ADD CONSTRAINT users_tenants_user_id_fkey FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

ALTER TABLE users_tenants ADD CONSTRAINT users_tenants_role_id_fkey FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE;

ALTER TABLE groups_tenants ALTER COLUMN role_id DROP NOT NULL;

ALTER TABLE deployment_updates ADD CONSTRAINT deployment_updates__old_blueprint_fk_fkey FOREIGN KEY(_old_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE CASCADE;

ALTER TABLE deployment_updates ADD CONSTRAINT deployment_updates__new_blueprint_fk_fkey FOREIGN KEY(_new_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE CASCADE;

CREATE INDEX blueprints__tenant_id_idx ON blueprints (_tenant_id);

CREATE INDEX deployment_modifications__tenant_id_idx ON deployment_modifications (_tenant_id);

CREATE INDEX deployment_update_steps__tenant_id_idx ON deployment_update_steps (_tenant_id);

CREATE INDEX deployment_updates__tenant_id_idx ON deployment_updates (_tenant_id);

CREATE INDEX deployments__tenant_id_idx ON deployments (_tenant_id);

CREATE INDEX events__tenant_id_idx ON events (_tenant_id);

CREATE INDEX executions__tenant_id_idx ON executions (_tenant_id);

CREATE INDEX logs__tenant_id_idx ON logs (_tenant_id);

CREATE INDEX nodes__tenant_id_idx ON nodes (_tenant_id);

CREATE INDEX node_instances__tenant_id_idx ON node_instances (_tenant_id);

CREATE INDEX plugins__tenant_id_idx ON plugins (_tenant_id);

CREATE INDEX snapshots__tenant_id_idx ON snapshots (_tenant_id);

CREATE INDEX secrets__tenant_id_idx ON secrets (_tenant_id);

DROP INDEX ix_blueprints_created_at;

DROP INDEX ix_blueprints_id;

DROP INDEX ix_deployment_modifications_created_at;

DROP INDEX ix_deployment_modifications_ended_at;

DROP INDEX ix_deployment_modifications_id;

DROP INDEX ix_deployment_update_steps_id;

DROP INDEX ix_deployment_updates_created_at;

DROP INDEX ix_deployment_updates_id;

DROP INDEX ix_deployments_created_at;

DROP INDEX ix_deployments_id;

DROP INDEX ix_events_id;

DROP INDEX ix_logs_id;

DROP INDEX ix_executions_created_at;

DROP INDEX ix_executions_id;

DROP INDEX ix_groups_ldap_dn;

DROP INDEX ix_groups_name;

DROP INDEX ix_node_instances_id;

DROP INDEX ix_nodes_id;

DROP INDEX ix_nodes_type;

DROP INDEX ix_plugins_archive_name;

DROP INDEX ix_plugins_id;

DROP INDEX ix_plugins_package_name;

DROP INDEX ix_plugins_uploaded_at;

DROP INDEX ix_secrets_created_at;

DROP INDEX ix_secrets_id;

DROP INDEX ix_snapshots_created_at;

DROP INDEX ix_snapshots_id;

DROP INDEX ix_tenants_name;

DROP INDEX ix_users_username;

DROP INDEX ix_roles_name;

UPDATE alembic_version SET version_num='a6d00b128933' WHERE alembic_version.version_num = 'c7652b2a97a4';

-- Running upgrade a6d00b128933 -> 1fbd6bf39e84

UPDATE users
      SET failed_logins_counter = 0
      WHERE failed_logins_counter IS NULL;;

ALTER TABLE users ALTER COLUMN failed_logins_counter SET NOT NULL;

ALTER TABLE executions ADD COLUMN is_dry_run BOOLEAN DEFAULT 'f' NOT NULL;

ALTER TABLE executions ADD COLUMN scheduled_for TIMESTAMP WITHOUT TIME ZONE;

COMMIT;

alter type execution_status add value 'scheduled';

BEGIN;

ALTER TABLE deployments ADD COLUMN capabilities BYTEA;

ALTER TABLE events ADD COLUMN source_id TEXT;

ALTER TABLE events ADD COLUMN target_id TEXT;

ALTER TABLE logs ADD COLUMN source_id TEXT;

ALTER TABLE logs ADD COLUMN target_id TEXT;

CREATE TYPE agent_states AS ENUM ('creating', 'created', 'configuring', 'configured', 'starting', 'started', 'stopping', 'stopped', 'deleting', 'deleted', 'restarting', 'restarted', 'upgrading', 'upgraded', 'failed', 'nonresponsive', 'restored');

CREATE TABLE agents (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    name TEXT NOT NULL, 
    ip TEXT, 
    install_method TEXT NOT NULL, 
    system TEXT, 
    version TEXT NOT NULL, 
    state agent_states NOT NULL, 
    visibility visibility_states, 
    rabbitmq_username TEXT, 
    rabbitmq_password TEXT, 
    rabbitmq_exchange TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _node_instance_fk INTEGER NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    PRIMARY KEY (_storage_id), 
    FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(_node_instance_fk) REFERENCES node_instances (_storage_id) ON DELETE CASCADE, 
    FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX agents__tenant_id_idx ON agents (_tenant_id);

CREATE INDEX agents_created_at_idx ON agents (created_at);

CREATE INDEX agents_id_idx ON agents (id);

ALTER TABLE blueprints DROP COLUMN private_resource;

ALTER TABLE plugins DROP COLUMN private_resource;

ALTER TABLE secrets DROP COLUMN private_resource;

ALTER TABLE snapshots DROP COLUMN private_resource;

ALTER TABLE events DROP COLUMN private_resource;

ALTER TABLE executions DROP COLUMN private_resource;

ALTER TABLE logs DROP COLUMN private_resource;

ALTER TABLE nodes DROP COLUMN private_resource;

ALTER TABLE node_instances DROP COLUMN private_resource;

ALTER TABLE deployments DROP COLUMN private_resource;

ALTER TABLE deployment_modifications DROP COLUMN private_resource;

ALTER TABLE deployment_updates DROP COLUMN private_resource;

ALTER TABLE deployment_update_steps DROP COLUMN private_resource;

CREATE TABLE tasks_graphs (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    name TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    _execution_fk INTEGER NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT tasks_graphs_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT tasks_graphs__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT tasks_graphs__execution_fk_fkey FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT tasks_graphs__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX tasks_graphs__tenant_id_idx ON tasks_graphs (_tenant_id);

CREATE INDEX tasks_graphs_created_at_idx ON tasks_graphs (created_at);

CREATE INDEX tasks_graphs_id_idx ON tasks_graphs (id);

CREATE TABLE operations (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    name TEXT, 
    state TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    dependencies TEXT[], 
    type TEXT, 
    parameters TEXT, 
    _tasks_graph_fk INTEGER NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT operations_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT operations__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT operations__tasks_graph_fk_fkey FOREIGN KEY(_tasks_graph_fk) REFERENCES tasks_graphs (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT operations__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX operations__tenant_id_idx ON operations (_tenant_id);

CREATE INDEX operations_created_at_idx ON operations (created_at);

CREATE INDEX operations_id_idx ON operations (id);

UPDATE alembic_version SET version_num='1fbd6bf39e84' WHERE alembic_version.version_num = 'a6d00b128933';

-- Running upgrade 1fbd6bf39e84 -> 9516df019579

CREATE TABLE licenses (
    id SERIAL NOT NULL, 
    customer_id TEXT, 
    expiration_date TIMESTAMP WITHOUT TIME ZONE, 
    license_edition VARCHAR(255), 
    trial BOOLEAN NOT NULL, 
    cloudify_version TEXT, 
    capabilities TEXT[], 
    signature BYTEA, 
    CONSTRAINT licenses_pkey PRIMARY KEY (id), 
    CONSTRAINT licenses_customer_id_key UNIQUE (customer_id)
);

UPDATE alembic_version SET version_num='9516df019579' WHERE alembic_version.version_num = '1fbd6bf39e84';

-- Running upgrade 9516df019579 -> 423a1643f365

ALTER TABLE executions ADD COLUMN token VARCHAR(100);

CREATE TABLE config (
    name TEXT NOT NULL, 
    value TEXT NOT NULL, 
    schema TEXT, 
    is_editable BOOLEAN, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    scope TEXT NOT NULL, 
    _updater_id INTEGER, 
    PRIMARY KEY (name, scope), 
    FOREIGN KEY(_updater_id) REFERENCES users (id) ON DELETE SET NULL
);

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('rest_service_log_path', '"/var/log/cloudify/rest/cloudify-rest-service.log"', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('rest_service_log_level', '"INFO"', '{"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_server', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_username', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_password', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_domain', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_is_active_directory', 'null', '{"type": "boolean"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_dn_extra', 'null', NULL, true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_timeout', '5.0', '{"type": "number"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_nested_levels', '1', '{"type": "number", "minimum": 1}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('file_server_root', '"/opt/manager/resources"', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('file_server_url', '"http://127.0.0.1:53333/resources"', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('insecure_endpoints_disabled', 'true', '{"type": "boolean"}', false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('maintenance_folder', '"/opt/manager/maintenance"', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('min_available_memory_mb', '100', '{"type": "number", "minimum": 0}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('failed_logins_before_account_lock', '4', '{"type": "number", "minimum": 1}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('account_lock_period', '-1', '{"type": "number", "minimum": -1}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('public_ip', 'null', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('default_page_size', '1000', '{"type": "number", "minimum": 1}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('max_workers', '5', '{"type": "number", "minimum": 1}', true, 'mgmtworker');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('min_workers', '2', '{"type": "number", "minimum": 1}', true, 'mgmtworker');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('broker_port', '5671', '{"type": "number", "minimum": 1, "maximum": 65535}', true, 'agent');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('min_workers', '2', '{"type": "number", "minimum": 1}', true, 'agent');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('max_workers', '5', '{"type": "number", "minimum": 1}', true, 'agent');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('heartbeat', '30', '{"type": "number", "minimum": 0}', true, 'agent');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('log_level', '"info"', '{"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]}', true, 'agent');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('task_retries', '60', '{"type": "number", "minimum": -1}', true, 'workflow');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('task_retry_interval', '15', '{"type": "number", "minimum": 0}', true, 'workflow');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('subgraph_retries', '0', '{"type": "number", "minimum": -1}', true, 'workflow');

CREATE TABLE certificates (
    id SERIAL NOT NULL, 
    name TEXT NOT NULL, 
    value TEXT NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _updater_id INTEGER, 
    CONSTRAINT certificates_pkey PRIMARY KEY (id), 
    FOREIGN KEY(_updater_id) REFERENCES users (id) ON DELETE SET NULL, 
    UNIQUE (name)
);

CREATE TABLE managers (
    id SERIAL NOT NULL, 
    hostname TEXT NOT NULL, 
    private_ip TEXT NOT NULL, 
    public_ip TEXT NOT NULL, 
    version TEXT NOT NULL, 
    edition TEXT NOT NULL, 
    distribution TEXT NOT NULL, 
    distro_release TEXT NOT NULL, 
    fs_sync_node_id TEXT, 
    networks TEXT, 
    _ca_cert_id INTEGER NOT NULL, 
    CONSTRAINT managers_pkey PRIMARY KEY (id), 
    FOREIGN KEY(_ca_cert_id) REFERENCES certificates (id) ON DELETE CASCADE, 
    UNIQUE (hostname), 
    UNIQUE (private_ip), 
    UNIQUE (public_ip)
);

CREATE TABLE rabbitmq_brokers (
    name TEXT NOT NULL, 
    host TEXT NOT NULL, 
    management_host TEXT, 
    port INTEGER, 
    username TEXT, 
    password TEXT, 
    params TEXT, 
    networks TEXT, 
    _ca_cert_id INTEGER NOT NULL, 
    CONSTRAINT rabbitmq_brokers_pkey PRIMARY KEY (name), 
    FOREIGN KEY(_ca_cert_id) REFERENCES certificates (id) ON DELETE CASCADE
);

ALTER TABLE deployment_updates ADD COLUMN central_plugins_to_install BYTEA;

ALTER TABLE deployment_updates ADD COLUMN central_plugins_to_uninstall BYTEA;

ALTER TABLE blueprints ADD COLUMN is_hidden BOOLEAN DEFAULT 'f' NOT NULL;

CREATE TABLE sites (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    name TEXT NOT NULL, 
    latitude FLOAT, 
    longitude FLOAT, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT sites_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT sites__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT sites__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX sites__tenant_id_idx ON sites (_tenant_id);

CREATE INDEX sites_created_at_idx ON sites (created_at);

CREATE INDEX sites_id_idx ON sites (id);

ALTER TABLE deployments ADD COLUMN _site_fk INTEGER;

ALTER TABLE deployments ADD CONSTRAINT deployments__site_fk_fkey FOREIGN KEY(_site_fk) REFERENCES sites (_storage_id) ON DELETE SET NULL;

CREATE TABLE plugins_updates (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    state TEXT, 
    deployments_to_update BYTEA, 
    forced BOOLEAN, 
    _original_blueprint_fk INTEGER NOT NULL, 
    _temp_blueprint_fk INTEGER, 
    _execution_fk INTEGER, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT plugins_updates_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT plugins_updates__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT plugins_updates__execution_fk_fkey FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE SET NULL, 
    CONSTRAINT plugins_updates__original_blueprint_fk_fkey FOREIGN KEY(_original_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT plugins_updates__temp_blueprint_fk_fkey FOREIGN KEY(_temp_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE SET NULL, 
    CONSTRAINT plugins_updates__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX plugins_updates__tenant_id_idx ON plugins_updates (_tenant_id);

CREATE INDEX plugins_updates_created_at_idx ON plugins_updates (created_at);

CREATE INDEX plugins_updates_id_idx ON plugins_updates (id);

UPDATE alembic_version SET version_num='423a1643f365' WHERE alembic_version.version_num = '9516df019579';

-- Running upgrade 423a1643f365 -> 62a8d746d13b

ALTER TABLE executions ADD COLUMN blueprint_id TEXT;

ALTER TABLE deployments ADD COLUMN runtime_only_evaluation BOOLEAN;

ALTER TABLE deployment_updates ADD COLUMN runtime_only_evaluation BOOLEAN;

ALTER TABLE node_instances ADD COLUMN index INTEGER;

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_ca_path', 'null', '{"type": "string"}', true, 'rest');

CREATE TABLE db_nodes (
    name TEXT NOT NULL, 
    node_id TEXT NOT NULL, 
    host TEXT NOT NULL, 
    is_external BOOLEAN DEFAULT 'f' NOT NULL, 
    CONSTRAINT db_nodes_pkey PRIMARY KEY (name), 
    CONSTRAINT db_nodes_node_id_key UNIQUE (node_id), 
    CONSTRAINT db_nodes_host_key UNIQUE (host)
);

ALTER TABLE managers ADD COLUMN node_id TEXT;

ALTER TABLE managers ADD COLUMN last_seen TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL;

ALTER TABLE managers ADD COLUMN status_report_frequency INTEGER;

UPDATE managers
      SET node_id = hostname;;

ALTER TABLE managers ALTER COLUMN node_id SET NOT NULL;

ALTER TABLE managers ADD CONSTRAINT managers_node_id_key UNIQUE (node_id);

CREATE INDEX managers_last_seen_idx ON managers (last_seen);

ALTER TABLE rabbitmq_brokers ADD COLUMN is_external BOOLEAN DEFAULT 'f' NOT NULL;

ALTER TABLE rabbitmq_brokers ADD COLUMN node_id TEXT;

UPDATE rabbitmq_brokers
      SET node_id = name;;

ALTER TABLE rabbitmq_brokers ALTER COLUMN node_id SET NOT NULL;

ALTER TABLE rabbitmq_brokers ADD CONSTRAINT rabbitmq_brokers_node_id_key UNIQUE (node_id);

CREATE INDEX node_instances__node_fk_idx ON node_instances (_node_fk);

CREATE INDEX nodes__deployment_fk_idx ON nodes (_deployment_fk);

CREATE INDEX executions_ended_at_idx ON executions (ended_at);

CREATE INDEX executions_token_idx ON executions (token);

CREATE INDEX agents__creator_id_idx ON agents (_creator_id);

CREATE INDEX agents__node_instance_fk_idx ON agents (_node_instance_fk);

CREATE INDEX agents_visibility_idx ON agents (visibility);

CREATE INDEX blueprints__creator_id_idx ON blueprints (_creator_id);

CREATE INDEX blueprints_visibility_idx ON blueprints (visibility);

CREATE INDEX certificates__updater_id_idx ON certificates (_updater_id);

CREATE INDEX config__updater_id_idx ON config (_updater_id);

CREATE INDEX deployment_modifications__creator_id_idx ON deployment_modifications (_creator_id);

CREATE INDEX deployment_modifications__deployment_fk_idx ON deployment_modifications (_deployment_fk);

CREATE INDEX deployment_modifications_visibility_idx ON deployment_modifications (visibility);

CREATE INDEX deployment_update_steps__creator_id_idx ON deployment_update_steps (_creator_id);

CREATE INDEX deployment_update_steps__deployment_update_fk_idx ON deployment_update_steps (_deployment_update_fk);

CREATE INDEX deployment_update_steps_visibility_idx ON deployment_update_steps (visibility);

CREATE INDEX deployment_updates__creator_id_idx ON deployment_updates (_creator_id);

CREATE INDEX deployment_updates__deployment_fk_idx ON deployment_updates (_deployment_fk);

CREATE INDEX deployment_updates__execution_fk_idx ON deployment_updates (_execution_fk);

CREATE INDEX deployment_updates__new_blueprint_fk_idx ON deployment_updates (_new_blueprint_fk);

CREATE INDEX deployment_updates__old_blueprint_fk_idx ON deployment_updates (_old_blueprint_fk);

CREATE INDEX deployment_updates_visibility_idx ON deployment_updates (visibility);

CREATE INDEX deployments__blueprint_fk_idx ON deployments (_blueprint_fk);

CREATE INDEX deployments__creator_id_idx ON deployments (_creator_id);

CREATE INDEX deployments__site_fk_idx ON deployments (_site_fk);

CREATE INDEX deployments_visibility_idx ON deployments (visibility);

CREATE INDEX events__creator_id_idx ON events (_creator_id);

CREATE INDEX events_visibility_idx ON events (visibility);

CREATE INDEX executions__creator_id_idx ON executions (_creator_id);

CREATE INDEX executions__deployment_fk_idx ON executions (_deployment_fk);

CREATE INDEX executions_visibility_idx ON executions (visibility);

CREATE INDEX groups_tenants_group_id_idx ON groups_tenants (group_id);

CREATE INDEX groups_tenants_role_id_idx ON groups_tenants (role_id);

CREATE INDEX groups_tenants_tenant_id_idx ON groups_tenants (tenant_id);

CREATE INDEX logs__creator_id_idx ON logs (_creator_id);

CREATE INDEX logs_visibility_idx ON logs (visibility);

CREATE INDEX managers__ca_cert_id_idx ON managers (_ca_cert_id);

CREATE INDEX node_instances__creator_id_idx ON node_instances (_creator_id);

CREATE INDEX node_instances_visibility_idx ON node_instances (visibility);

CREATE INDEX nodes__creator_id_idx ON nodes (_creator_id);

CREATE INDEX nodes_visibility_idx ON nodes (visibility);

CREATE INDEX operations__creator_id_idx ON operations (_creator_id);

CREATE INDEX operations__tasks_graph_fk_idx ON operations (_tasks_graph_fk);

CREATE INDEX operations_visibility_idx ON operations (visibility);

CREATE INDEX plugins__creator_id_idx ON plugins (_creator_id);

CREATE INDEX plugins_visibility_idx ON plugins (visibility);

CREATE INDEX plugins_updates__creator_id_idx ON plugins_updates (_creator_id);

CREATE INDEX plugins_updates__execution_fk_idx ON plugins_updates (_execution_fk);

CREATE INDEX plugins_updates__original_blueprint_fk_idx ON plugins_updates (_original_blueprint_fk);

CREATE INDEX plugins_updates__temp_blueprint_fk_idx ON plugins_updates (_temp_blueprint_fk);

CREATE INDEX plugins_updates_visibility_idx ON plugins_updates (visibility);

CREATE INDEX rabbitmq_brokers__ca_cert_id_idx ON rabbitmq_brokers (_ca_cert_id);

CREATE INDEX secrets__creator_id_idx ON secrets (_creator_id);

CREATE INDEX secrets_visibility_idx ON secrets (visibility);

CREATE INDEX sites__creator_id_idx ON sites (_creator_id);

CREATE INDEX sites_visibility_idx ON sites (visibility);

CREATE INDEX snapshots__creator_id_idx ON snapshots (_creator_id);

CREATE INDEX snapshots_visibility_idx ON snapshots (visibility);

CREATE INDEX tasks_graphs__creator_id_idx ON tasks_graphs (_creator_id);

CREATE INDEX tasks_graphs__execution_fk_idx ON tasks_graphs (_execution_fk);

CREATE INDEX tasks_graphs_visibility_idx ON tasks_graphs (visibility);

CREATE INDEX users_tenants_role_id_idx ON users_tenants (role_id);

CREATE INDEX users_tenants_tenant_id_idx ON users_tenants (tenant_id);

CREATE INDEX users_tenants_user_id_idx ON users_tenants (user_id);

CREATE INDEX events_node_id_idx ON events (node_id);

CREATE INDEX executions_is_system_workflow_idx ON executions (is_system_workflow);

CREATE INDEX logs_node_id_idx ON logs (node_id);

CREATE INDEX node_instances_state_idx ON node_instances (state);

CREATE INDEX tasks_graphs_name_idx ON tasks_graphs (name);

CREATE INDEX deployments__sife_fk_visibility_idx ON deployments (_blueprint_fk, _site_fk, visibility, _tenant_id);

CREATE INDEX events_node_id_visibility_idx ON events (node_id, visibility);

CREATE INDEX executions_dep_fk_isw_vis_tenant_id_idx ON executions (_deployment_fk, is_system_workflow, visibility, _tenant_id);

CREATE INDEX logs_node_id_visibility_execution_fk_idx ON logs (node_id, visibility, _execution_fk);

CREATE INDEX node_instances_state_visibility_idx ON node_instances (state, visibility);

CREATE INDEX tasks_graphs__execution_fk_name_visibility_idx ON tasks_graphs (_execution_fk, name, visibility);

ALTER TABLE users_roles ADD CONSTRAINT users_roles_pkey PRIMARY KEY (user_id, role_id);

UPDATE alembic_version SET version_num='62a8d746d13b' WHERE alembic_version.version_num = '423a1643f365';

-- Running upgrade 62a8d746d13b -> 387fcd049efb

CREATE TABLE usage_collector (
    id SERIAL NOT NULL, 
    manager_id TEXT NOT NULL, 
    hourly_timestamp INTEGER, 
    daily_timestamp INTEGER, 
    hours_interval INTEGER NOT NULL, 
    days_interval INTEGER NOT NULL, 
    CONSTRAINT usage_collector_pkey PRIMARY KEY (id), 
    CONSTRAINT usage_collector_manager_id_key UNIQUE (manager_id)
);

CREATE TABLE inter_deployment_dependencies (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    dependency_creator TEXT NOT NULL, 
    target_deployment_func TEXT, 
    _source_deployment INTEGER, 
    _target_deployment INTEGER, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    external_source TEXT, 
    external_target TEXT, 
    CONSTRAINT inter_deployment_dependencies_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT inter_deployment_dependencies__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT inter_deployment_dependencies__source_deployment_fkey FOREIGN KEY(_source_deployment) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT inter_deployment_dependencies__target_deployment_fkey FOREIGN KEY(_target_deployment) REFERENCES deployments (_storage_id) ON DELETE SET NULL, 
    CONSTRAINT inter_deployment_dependencies__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX inter_deployment_dependencies__tenant_id_idx ON inter_deployment_dependencies (_tenant_id);

CREATE INDEX inter_deployment_dependencies_created_at_idx ON inter_deployment_dependencies (created_at);

CREATE UNIQUE INDEX inter_deployment_dependencies_id_idx ON inter_deployment_dependencies (id);

CREATE INDEX inter_deployment_dependencies__creator_id_idx ON inter_deployment_dependencies (_creator_id);

CREATE INDEX inter_deployment_dependencies_visibility_idx ON inter_deployment_dependencies (visibility);

CREATE INDEX inter_deployment_dependencies__source_deployment_idx ON inter_deployment_dependencies (_source_deployment);

CREATE INDEX inter_deployment_dependencies__target_deployment_idx ON inter_deployment_dependencies (_target_deployment);

ALTER TABLE deployment_updates ADD COLUMN keep_old_deployment_dependencies BOOLEAN DEFAULT true NOT NULL;

CREATE UNIQUE INDEX blueprints_id__tenant_id_idx ON blueprints (id, _tenant_id);

CREATE INDEX deployments__site_fk_visibility_idx ON deployments (_blueprint_fk, _site_fk, visibility, _tenant_id);

CREATE UNIQUE INDEX deployments_id__tenant_id_idx ON deployments (id, _tenant_id);

DROP INDEX deployments__sife_fk_visibility_idx;

CREATE UNIQUE INDEX plugins_name_version__tenant_id_idx ON plugins (package_name, package_version, _tenant_id, distribution, distribution_release, distribution_version);

CREATE UNIQUE INDEX secrets_id_tenant_id_idx ON secrets (id, _tenant_id);

CREATE UNIQUE INDEX site_name__tenant_id_idx ON sites (name, _tenant_id);

CREATE UNIQUE INDEX snapshots_id__tenant_id_idx ON snapshots (id, _tenant_id);

DROP INDEX tasks_graphs__execution_fk_name_visibility_idx;

CREATE UNIQUE INDEX tasks_graphs__execution_fk_name_visibility_idx ON tasks_graphs (_execution_fk, name, visibility);

ALTER TABLE plugins ADD COLUMN title TEXT;

ALTER TABLE db_nodes DROP CONSTRAINT db_nodes_node_id_key;

ALTER TABLE db_nodes DROP COLUMN node_id;

ALTER TABLE managers DROP CONSTRAINT managers_node_id_key;

ALTER TABLE managers DROP COLUMN node_id;

ALTER TABLE rabbitmq_brokers DROP CONSTRAINT rabbitmq_brokers_node_id_key;

ALTER TABLE rabbitmq_brokers DROP COLUMN node_id;

ALTER TABLE db_nodes ADD COLUMN monitoring_password TEXT;

ALTER TABLE db_nodes ADD COLUMN monitoring_username TEXT;

ALTER TABLE managers ADD COLUMN monitoring_password TEXT;

ALTER TABLE managers ADD COLUMN monitoring_username TEXT;

ALTER TABLE rabbitmq_brokers ADD COLUMN monitoring_password TEXT;

ALTER TABLE rabbitmq_brokers ADD COLUMN monitoring_username TEXT;

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('service_management', '"systemd"', NULL, true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('blueprint_folder_max_size_mb', '50', '{"type": "number", "minimum": 0}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('blueprint_folder_max_files', '10000', '{"type": "number", "minimum": 0}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('monitoring_timeout', '4', '{"type": "number", "minimum": 0}', true, 'rest');

CREATE TABLE plugins_states (
    _storage_id SERIAL NOT NULL, 
    _plugin_fk INTEGER NOT NULL, 
    _manager_fk INTEGER, 
    _agent_fk INTEGER, 
    state TEXT, 
    error TEXT, 
    CONSTRAINT plugins_states_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT plugins_states__agent_fk_fkey FOREIGN KEY(_agent_fk) REFERENCES agents (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT plugins_states__manager_fk_fkey FOREIGN KEY(_manager_fk) REFERENCES managers (id) ON DELETE CASCADE, 
    CONSTRAINT plugins_states__plugin_fk_fkey FOREIGN KEY(_plugin_fk) REFERENCES plugins (_storage_id) ON DELETE CASCADE
);

CREATE INDEX plugins_states__agent_fk_idx ON plugins_states (_agent_fk);

CREATE INDEX plugins_states__manager_fk_idx ON plugins_states (_manager_fk);

CREATE INDEX plugins_states__plugin_fk_idx ON plugins_states (_plugin_fk);

ALTER TABLE plugins_states ADD CONSTRAINT plugins_states_manager_or_agent CHECK ((_agent_fk IS NULL) != (_manager_fk IS NULL));

UPDATE alembic_version SET version_num='387fcd049efb' WHERE alembic_version.version_num = '62a8d746d13b';

-- Running upgrade 387fcd049efb -> 5ce2b0cbb6f3

ALTER TABLE deployment_update_steps ADD COLUMN topology_order INTEGER DEFAULT '0' NOT NULL;

CREATE TABLE deployments_labels (
    id SERIAL NOT NULL, 
    key TEXT NOT NULL, 
    value TEXT NOT NULL, 
    _deployment_fk INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT deployments_labels_pkey PRIMARY KEY (id), 
    CONSTRAINT deployments_labels__deployment_fk FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT deployments_labels__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT "{0}_key_value_key" UNIQUE (key, value, _deployment_fk)
);

CREATE INDEX deployments_labels_created_at_idx ON deployments_labels (created_at);

CREATE INDEX deployments_labels__creator_id_idx ON deployments_labels (_creator_id);

CREATE INDEX deployments_labels_key_idx ON deployments_labels (key);

CREATE INDEX deployments_labels__deployment_idx ON deployments_labels (_deployment_fk);

CREATE TABLE permissions (
    id SERIAL NOT NULL, 
    role_id INTEGER NOT NULL, 
    name TEXT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

INSERT INTO permissions (name, role_id) SELECT 'all_tenants' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'administrators' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'administrators' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_global_resource' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'getting_started' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'agent_replace_certs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'blueprint_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'cluster_node_config_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modify' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modify' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modify' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modify' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_site' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_site' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_site' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_site' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_finish' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_finish' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_finish' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_finish' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_rollback' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_rollback' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_rollback' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_rollback' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_modification_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_capabilities' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_capabilities' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_capabilities' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_capabilities' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_capabilities' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_update_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_group_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'event_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execute_global_workflow' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execute_global_workflow' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_schedule_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_cancel' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'set_execution_group_details' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'file_server_auth' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'file_server_auth' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'file_server_auth' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'file_server_auth' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'file_server_auth' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'functions_evaluate' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'functions_evaluate' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'functions_evaluate' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'functions_evaluate' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_set' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'ldap_status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'maintenance_mode_set' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_put' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_config_put' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manager_manage' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_manage' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'broker_credentials' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'db_nodes_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'node_instance_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'operations' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'operations' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'operations' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'operations' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'operations' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugin_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'plugins_update_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'provider_context_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_export' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_export' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_export' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_import' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_import' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'secret_import' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'status_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'site_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_rabbitmq_credentials' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_rabbitmq_credentials' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_rabbitmq_credentials' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_rabbitmq_credentials' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_list_get_data' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_add_user' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_update_user' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_remove_user' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_add_group' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_update_group' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'tenant_remove_group' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'token_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_get_self' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_set_activated' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_unlock' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_add_user' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_group_remove_user' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'version_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'snapshot_restore' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'resource_set_global' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'resource_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'resource_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'resource_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'deployment_set_visibility' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inter_deployment_dependency_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'labels_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'labels_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'labels_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'labels_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'labels_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'filter_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_services_status' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_edit_mode' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_edit_mode' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_edit_mode' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_edit_mode' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_maintenance_mode' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_configure' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_template_management' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'stage_install_widgets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_admin' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_admin' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_sys_admin' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_all' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_all' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_all' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_all' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_custom_all' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_agents' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_agents' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_agents' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_agents' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_agents' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprints' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprints' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprints' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprints' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprints' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintSources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintSources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintSources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintSources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintSources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_blueprintUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_buttonLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_buttonLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_buttonLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_buttonLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_buttonLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_composerLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_composerLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_composerLink' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_cloudNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_cloudNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_cloudNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_cloudNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_cloudNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentActionButtons' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentInfo' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deployments' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deployments' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deployments' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deployments' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deployments' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentsView' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentsView' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentsView' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentsView' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_deploymentsView' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_events' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_events' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_events' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_events' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_events' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_eventsFilter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_eventsFilter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_eventsFilter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_eventsFilter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_eventsFilter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executions' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executions' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executions' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executions' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executions' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionsStatus' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionsStatus' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionsStatus' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionsStatus' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_executionsStatus' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filter' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filters' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filters' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filters' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filters' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_filters' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_highAvailability' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_inputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_inputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_inputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_inputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_inputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_labels' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_labels' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_labels' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_labels' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_labels' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_maintenanceModeButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_managers' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodes' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodes' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodes' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodes' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodes' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesComputeNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesComputeNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesComputeNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesComputeNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesComputeNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesStats' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesStats' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesStats' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesStats' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_nodesStats' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_onlyMyResources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_onlyMyResources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_onlyMyResources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_onlyMyResources' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_outputs' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_plugins' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_plugins' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_plugins' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_plugins' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_plugins' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsCatalog' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginsNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_pluginUploadButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_secrets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_secrets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_secrets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_secrets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_secrets' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serversNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serversNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serversNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serversNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serversNum' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serviceButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serviceButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serviceButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_serviceButton' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sites' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sites' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sites' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sites' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sites' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sitesMap' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sitesMap' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sitesMap' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sitesMap' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_sitesMap' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_snapshots' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tenants' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_text' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_text' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_text' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_text' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_text' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_topology' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_topology' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_topology' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_topology' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_topology' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_userGroups' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'widget_userManagement' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'user_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_should_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_should_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_should_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_should_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'execution_should_start' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_upload' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_remove' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'license_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'get_password_hash' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'set_timestamp' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'set_owner' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'set_execution_details' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'audit_log_view' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'audit_log_truncate' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'audit_log_inject' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'set_plugin_update_details' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'operations' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'identity_provider_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'community_contact_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'create_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'delete_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'delete_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'delete_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'delete_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'delete_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'list_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'list_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'manager' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'list_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'user' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'list_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'default' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'list_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'viewer' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'manage_others_tokens' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'inject_token' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_list' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_get' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_create' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_delete' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_status_update' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

INSERT INTO permissions (name, role_id) SELECT 'log_bundle_download' AS name, roles.id 
FROM roles 
WHERE roles.name = 'sys_admin' 
 LIMIT 1;

CREATE TABLE maintenance_mode (
    id SERIAL NOT NULL, 
    status TEXT NOT NULL, 
    activation_requested_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    activated_at TIMESTAMP WITHOUT TIME ZONE, 
    _requested_by INTEGER, 
    CONSTRAINT maintenance_mode_pkey PRIMARY KEY (id), 
    CONSTRAINT maintenance_mode__requested_by_fkey FOREIGN KEY(_requested_by) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX maintenance_mode__requested_by_idx ON maintenance_mode (_requested_by);

ALTER TABLE roles ADD COLUMN type TEXT DEFAULT 'tenant_role' NOT NULL;

UPDATE alembic_version SET version_num='5ce2b0cbb6f3' WHERE alembic_version.version_num = '387fcd049efb';

-- Running upgrade 5ce2b0cbb6f3 -> 9d261e90b1f3

ALTER TABLE blueprints ADD COLUMN state TEXT;

ALTER TABLE blueprints ADD COLUMN error TEXT;

ALTER TABLE blueprints ADD COLUMN error_traceback TEXT;

ALTER TABLE blueprints ALTER COLUMN main_file_name DROP NOT NULL;

ALTER TABLE blueprints ALTER COLUMN plan DROP NOT NULL;

update blueprints set state='uploaded';

CREATE TABLE filters (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    value TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT filters_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT filters__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT filters__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX filters__tenant_id_idx ON filters (_tenant_id);

CREATE INDEX filters_created_at_idx ON filters (created_at);

CREATE INDEX filters_id_idx ON filters (id);

CREATE INDEX filters__creator_id_idx ON filters (_creator_id);

CREATE INDEX filters_visibility_idx ON filters (visibility);

CREATE UNIQUE INDEX filters_id__tenant_id_idx ON filters (id, _tenant_id);

CREATE TABLE deployment_groups (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    description TEXT, 
    _default_blueprint_fk INTEGER, 
    default_inputs TEXT, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT deployment_groups_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT deployment_groups__default_blueprint_fk_fkey FOREIGN KEY(_default_blueprint_fk) REFERENCES blueprints (_storage_id) ON DELETE SET NULL, 
    CONSTRAINT deployment_groups__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT deployment_groups__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX deployment_groups__default_blueprint_fk_idx ON deployment_groups (_default_blueprint_fk);

CREATE INDEX deployment_groups__creator_id_idx ON deployment_groups (_creator_id);

CREATE INDEX deployment_groups__tenant_id_idx ON deployment_groups (_tenant_id);

CREATE INDEX deployment_groups_created_at_idx ON deployment_groups (created_at);

CREATE INDEX deployment_groups_id_idx ON deployment_groups (id);

CREATE INDEX deployment_groups_visibility_idx ON deployment_groups (visibility);

CREATE TABLE deployment_groups_deployments (
    deployment_group_id INTEGER, 
    deployment_id INTEGER, 
    CONSTRAINT deployment_groups_deployments_deployment_grou_id_fkey FOREIGN KEY(deployment_group_id) REFERENCES deployment_groups (_storage_id), 
    CONSTRAINT deployment_groups_deployments_deployment_id_fkey FOREIGN KEY(deployment_id) REFERENCES deployments (_storage_id)
);

CREATE TABLE execution_schedules (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    next_occurrence TIMESTAMP WITHOUT TIME ZONE, 
    since TIMESTAMP WITHOUT TIME ZONE, 
    until TIMESTAMP WITHOUT TIME ZONE, 
    rule TEXT NOT NULL, 
    slip INTEGER NOT NULL, 
    workflow_id TEXT NOT NULL, 
    parameters TEXT, 
    execution_arguments TEXT, 
    stop_on_fail BOOLEAN DEFAULT 'f' NOT NULL, 
    enabled BOOLEAN DEFAULT 't' NOT NULL, 
    _deployment_fk INTEGER NOT NULL, 
    _latest_execution_fk INTEGER, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT execution_schedules_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT execution_schedules__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT execution_schedules__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT execution_schedules__deployment_fkey FOREIGN KEY(_deployment_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE
);

ALTER TABLE execution_schedules ADD CONSTRAINT execution_schedules__latest_execution_fk_fkey FOREIGN KEY(_latest_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE;

CREATE INDEX execution_schedules_created_at_idx ON execution_schedules (created_at);

CREATE INDEX execution_schedules_id_idx ON execution_schedules (id);

CREATE INDEX execution_schedules__creator_id_idx ON execution_schedules (_creator_id);

CREATE INDEX execution_schedules__tenant_id_idx ON execution_schedules (_tenant_id);

CREATE INDEX execution_schedules_visibility_idx ON execution_schedules (visibility);

CREATE INDEX execution_schedules_next_occurrence_idx ON execution_schedules (next_occurrence);

CREATE INDEX execution_schedules__deployment_fk_idx ON execution_schedules (_deployment_fk);

CREATE INDEX execution_schedules__latest_execution_fk_idx ON execution_schedules (_latest_execution_fk);

alter table deployments_labels rename CONSTRAINT "{0}_key_value_key" to "deployments_labels_key_key";;

alter INDEX deployments_labels__deployment_idx RENAME TO deployments_labels__deployment_fk_idx;

CREATE INDEX deployments_labels_value_idx ON deployments_labels (value);

CREATE INDEX permissions_role_id_idx ON permissions (role_id);

DROP INDEX inter_deployment_dependencies_id_idx;

CREATE INDEX inter_deployment_dependencies_id_idx ON inter_deployment_dependencies (id);

CREATE TABLE execution_groups (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    _deployment_group_fk INTEGER, 
    workflow_id TEXT NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT execution_groups_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT execution_groups__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT execution_groups__deployment_group_fk_fkey FOREIGN KEY(_deployment_group_fk) REFERENCES deployment_groups (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT execution_groups__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX execution_groups__creator_id_idx ON execution_groups (_creator_id);

CREATE INDEX execution_groups__deployment_group_fk_idx ON execution_groups (_deployment_group_fk);

CREATE INDEX execution_groups__tenant_id_idx ON execution_groups (_tenant_id);

CREATE INDEX execution_groups_created_at_idx ON execution_groups (created_at);

CREATE INDEX execution_groups_id_idx ON execution_groups (id);

CREATE INDEX execution_groups_visibility_idx ON execution_groups (visibility);

CREATE TABLE execution_groups_executions (
    execution_group_id INTEGER, 
    execution_id INTEGER, 
    CONSTRAINT execution_groups_executions_execution_grou_id_fkey FOREIGN KEY(execution_group_id) REFERENCES execution_groups (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT execution_groups_executions_execution_id_fkey FOREIGN KEY(execution_id) REFERENCES executions (_storage_id) ON DELETE CASCADE
);

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_group_members_filter', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_attribute_group_membership', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_base_dn', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_group_dn', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_bind_format', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_user_filter', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_group_member_filter', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_attribute_email', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_attribute_first_name', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_attribute_last_name', 'null', '{"type": "string"}', true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('ldap_attribute_uid', 'null', '{"type": "string"}', true, 'rest');

ALTER TABLE maintenance_mode DROP CONSTRAINT maintenance_mode__requested_by_fkey;

ALTER TABLE maintenance_mode ADD CONSTRAINT maintenance_mode__requested_by_fkey FOREIGN KEY(_requested_by) REFERENCES users (id) ON DELETE SET NULL;

UPDATE alembic_version SET version_num='9d261e90b1f3' WHERE alembic_version.version_num = '5ce2b0cbb6f3';

-- Running upgrade 9d261e90b1f3 -> 396303c07e35

CREATE TABLE blueprints_labels (
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id SERIAL NOT NULL, 
    key TEXT NOT NULL, 
    value TEXT NOT NULL, 
    _labeled_model_fk INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT blueprints_labels_pkey PRIMARY KEY (id), 
    CONSTRAINT blueprints_labels__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT blueprints_labels__labeled_model_fk_fkey FOREIGN KEY(_labeled_model_fk) REFERENCES blueprints (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT blueprints_labels_key_key UNIQUE (key, value, _labeled_model_fk)
);

CREATE INDEX blueprints_labels__creator_id_idx ON blueprints_labels (_creator_id);

CREATE INDEX blueprints_labels__labeled_model_fk_idx ON blueprints_labels (_labeled_model_fk);

CREATE INDEX blueprints_labels_created_at_idx ON blueprints_labels (created_at);

CREATE INDEX blueprints_labels_key_idx ON blueprints_labels (key);

CREATE INDEX blueprints_labels_value_idx ON blueprints_labels (value);

ALTER TABLE deployments_labels ADD COLUMN _labeled_model_fk INTEGER;

UPDATE deployments_labels SET _labeled_model_fk=deployments_labels._deployment_fk WHERE deployments_labels._labeled_model_fk IS NULL;

ALTER TABLE deployments_labels ALTER COLUMN _labeled_model_fk SET NOT NULL;

DROP INDEX deployments_labels__deployment_fk_idx;

ALTER TABLE deployments_labels DROP CONSTRAINT deployments_labels_key_key;

ALTER TABLE deployments_labels ADD CONSTRAINT deployments_labels_key_key UNIQUE (key, value, _labeled_model_fk);

CREATE INDEX deployments_labels__labeled_model_fk_idx ON deployments_labels (_labeled_model_fk);

ALTER TABLE deployments_labels DROP CONSTRAINT deployments_labels__deployment_fk;

ALTER TABLE deployments_labels ADD CONSTRAINT deployments_labels__labeled_model_fk_fkey FOREIGN KEY(_labeled_model_fk) REFERENCES deployments (_storage_id) ON DELETE CASCADE;

ALTER TABLE deployments_labels DROP COLUMN _deployment_fk;

CREATE UNIQUE INDEX execution_schedules_id__deployment_fk_idx ON execution_schedules (id, _deployment_fk, _tenant_id);

ALTER TABLE execution_schedules ADD CONSTRAINT execution_schedules_id_key UNIQUE (id, _deployment_fk, _tenant_id);

ALTER TABLE blueprints ADD COLUMN _upload_execution_fk INTEGER;

CREATE INDEX blueprints__upload_execution_fk_idx ON blueprints (_upload_execution_fk);

ALTER TABLE blueprints ADD CONSTRAINT blueprints__upload_execution_fk_fkey FOREIGN KEY(_upload_execution_fk) REFERENCES executions (_storage_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE deployments ADD COLUMN _create_execution_fk INTEGER;

CREATE INDEX deployments__create_execution_fk_idx ON deployments (_create_execution_fk);

ALTER TABLE deployments ADD CONSTRAINT deployments__create_execution_fk_fkey FOREIGN KEY(_create_execution_fk) REFERENCES executions (_storage_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE deployments ADD COLUMN _latest_execution_fk INTEGER;

CREATE UNIQUE INDEX deployments__latest_execution_fk_idx ON deployments (_latest_execution_fk);

ALTER TABLE deployments ADD CONSTRAINT deployments__latest_execution_fk_fkey FOREIGN KEY(_latest_execution_fk) REFERENCES executions (_storage_id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE blueprints_filters (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    value TEXT, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    is_system_filter BOOLEAN DEFAULT 'f' NOT NULL, 
    CONSTRAINT blueprints_filters_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT blueprints_filters__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT blueprints_filters__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX blueprints_filters__creator_id_idx ON blueprints_filters (_creator_id);

CREATE INDEX blueprints_filters__tenant_id_idx ON blueprints_filters (_tenant_id);

CREATE INDEX blueprints_filters_created_at_idx ON blueprints_filters (created_at);

CREATE UNIQUE INDEX blueprints_filters_id__tenant_id_idx ON blueprints_filters (id, _tenant_id);

CREATE INDEX blueprints_filters_id_idx ON blueprints_filters (id);

CREATE INDEX blueprints_filters_visibility_idx ON blueprints_filters (visibility);

CREATE INDEX blueprints_filters_is_system_filter_idx ON blueprints_filters (is_system_filter);

CREATE TABLE deployments_filters (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    value TEXT, 
    updated_at TIMESTAMP WITHOUT TIME ZONE, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    is_system_filter BOOLEAN DEFAULT 'f' NOT NULL, 
    CONSTRAINT deployments_filters_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT deployments_filters__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT deployments_filters__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX deployments_filters__creator_id_idx ON deployments_filters (_creator_id);

CREATE INDEX deployments_filters__tenant_id_idx ON deployments_filters (_tenant_id);

CREATE INDEX deployments_filters_created_at_idx ON deployments_filters (created_at);

CREATE UNIQUE INDEX deployments_filters_id__tenant_id_idx ON deployments_filters (id, _tenant_id);

CREATE INDEX deployments_filters_id_idx ON deployments_filters (id);

CREATE INDEX deployments_filters_visibility_idx ON deployments_filters (visibility);

CREATE INDEX deployments_filters_is_system_filter_idx ON deployments_filters (is_system_filter);

DROP INDEX filters__creator_id_idx;

DROP INDEX filters__tenant_id_idx;

DROP INDEX filters_created_at_idx;

DROP INDEX filters_id__tenant_id_idx;

DROP INDEX filters_id_idx;

DROP INDEX filters_visibility_idx;

DROP TABLE filters;

CREATE TYPE installation_status AS ENUM ('active', 'inactive');

CREATE TYPE deployment_status AS ENUM ('good', 'in_progress', 'requires_attention');

ALTER TABLE deployments ADD COLUMN installation_status installation_status;

ALTER TABLE deployments ADD COLUMN deployment_status deployment_status;

ALTER TABLE execution_groups ADD COLUMN concurrency INTEGER DEFAULT '5' NOT NULL;

ALTER TABLE executions ADD COLUMN finished_operations INTEGER;

ALTER TABLE executions ADD COLUMN total_operations INTEGER;

ALTER TABLE executions ADD COLUMN resume BOOLEAN DEFAULT 'false' NOT NULL;

CREATE TABLE deployment_labels_dependencies (
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    _source_deployment INTEGER NOT NULL, 
    _target_deployment INTEGER NOT NULL, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT deployment_labels_dependencies_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT deployment_labels_dependencies__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT deployment_labels_dependencies__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE, 
    CONSTRAINT deployment_labels_dependencies__source_deployment_fkey FOREIGN KEY(_source_deployment) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT deployment_labels_dependencies__target_deployment_fkey FOREIGN KEY(_target_deployment) REFERENCES deployments (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT deployment_labels_dependencies__source_deployment_key UNIQUE (_source_deployment, _target_deployment)
);

CREATE INDEX deployment_labels_dependencies__creator_id_idx ON deployment_labels_dependencies (_creator_id);

CREATE INDEX deployment_labels_dependencies__tenant_id_idx ON deployment_labels_dependencies (_tenant_id);

CREATE INDEX deployment_labels_dependencies_created_at_idx ON deployment_labels_dependencies (created_at);

CREATE INDEX deployment_labels_dependencies_id_idx ON deployment_labels_dependencies (id);

CREATE INDEX deployment_labels_dependencies__source_deployment_idx ON deployment_labels_dependencies (_source_deployment);

CREATE INDEX deployment_labels_dependencies__target_deployment_idx ON deployment_labels_dependencies (_target_deployment);

CREATE INDEX deployment_labels_dependencies_visibility_idx ON deployment_labels_dependencies (visibility);

ALTER TABLE deployments ADD COLUMN sub_environments_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE deployments ADD COLUMN sub_environments_status deployment_status;

ALTER TABLE deployments ADD COLUMN sub_services_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE deployments ADD COLUMN sub_services_status deployment_status;

CREATE TABLE deployment_groups_labels (
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id SERIAL NOT NULL, 
    key TEXT NOT NULL, 
    value TEXT NOT NULL, 
    _labeled_model_fk INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT deployment_groups_labels_pkey PRIMARY KEY (id), 
    CONSTRAINT deployment_groups_labels__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT deployment_groups_labels__labeled_model_fk_fkey FOREIGN KEY(_labeled_model_fk) REFERENCES deployment_groups (_storage_id) ON DELETE CASCADE, 
    CONSTRAINT deployment_groups_labels_key_key UNIQUE (key, value, _labeled_model_fk)
);

CREATE INDEX deployment_groups_labels__creator_id_idx ON deployment_groups_labels (_creator_id);

CREATE INDEX deployment_groups_labels__labeled_model_fk_idx ON deployment_groups_labels (_labeled_model_fk);

CREATE INDEX deployment_groups_labels_created_at_idx ON deployment_groups_labels (created_at);

CREATE INDEX deployment_groups_labels_key_idx ON deployment_groups_labels (key);

CREATE INDEX deployment_groups_labels_value_idx ON deployment_groups_labels (value);

ALTER TABLE users ADD COLUMN show_getting_started BOOLEAN DEFAULT 't' NOT NULL;

ALTER TABLE users ADD COLUMN first_login_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE alembic_version SET version_num='396303c07e35' WHERE alembic_version.version_num = '9d261e90b1f3';

-- Running upgrade 396303c07e35 -> b92770a7b6ca

ALTER TABLE events ADD COLUMN _execution_group_fk INTEGER;

ALTER TABLE events ALTER COLUMN _execution_fk DROP NOT NULL;

CREATE INDEX events__execution_group_fk_idx ON events (_execution_group_fk);

ALTER TABLE events ADD CONSTRAINT events__execution_group_fk_fkey FOREIGN KEY(_execution_group_fk) REFERENCES execution_groups (_storage_id) ON DELETE CASCADE;

ALTER TABLE events ADD CONSTRAINT events__one_fk_not_null CHECK ((_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL));

ALTER TABLE logs ADD COLUMN _execution_group_fk INTEGER;

ALTER TABLE logs ALTER COLUMN _execution_fk DROP NOT NULL;

CREATE INDEX logs__execution_group_fk_idx ON logs (_execution_group_fk);

ALTER TABLE logs ADD CONSTRAINT logs__execution_group_fk_fkey FOREIGN KEY(_execution_group_fk) REFERENCES execution_groups (_storage_id) ON DELETE CASCADE;

ALTER TABLE logs ADD CONSTRAINT logs__one_fk_not_null CHECK ((_execution_fk IS NOT NULL) != (_execution_group_fk IS NOT NULL));

ALTER TABLE executions ADD COLUMN allow_custom_parameters BOOLEAN DEFAULT 'false' NOT NULL;

DROP INDEX events_id_idx;

ALTER TABLE events DROP COLUMN id;

DROP INDEX logs_id_idx;

ALTER TABLE logs DROP COLUMN id;

ALTER TABLE deployments ADD COLUMN display_name TEXT;

UPDATE deployments SET display_name=deployments.id;

ALTER TABLE deployments ALTER COLUMN display_name SET NOT NULL;

CREATE INDEX deployments_display_name_idx ON deployments (display_name);

ALTER TABLE deployment_groups ADD COLUMN creation_counter INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE execution_groups ADD COLUMN _success_group_fk INTEGER;

ALTER TABLE execution_groups ADD COLUMN _failed_group_fk INTEGER;

CREATE INDEX execution_groups__failed_group_fk_idx ON execution_groups (_failed_group_fk);

CREATE INDEX execution_groups__success_group_fk_idx ON execution_groups (_success_group_fk);

ALTER TABLE execution_groups ADD CONSTRAINT execution_groups__success_group_fk_fkey FOREIGN KEY(_success_group_fk) REFERENCES deployment_groups (_storage_id) ON DELETE SET NULL;

ALTER TABLE execution_groups ADD CONSTRAINT execution_groups__failed_group_fk_fkey FOREIGN KEY(_failed_group_fk) REFERENCES deployment_groups (_storage_id) ON DELETE SET NULL;

ALTER TABLE deployment_groups_deployments ADD CONSTRAINT deployment_groups_deployments_deployment_group_id_key UNIQUE (deployment_group_id, deployment_id);

UPDATE alembic_version SET version_num='b92770a7b6ca' WHERE alembic_version.version_num = '396303c07e35';

-- Running upgrade b92770a7b6ca -> a31cb9e704d3

UPDATE config SET schema='{"type": "integer", "minimum": 1, "maximum": 65535}' WHERE config.name = 'broker_port' AND config.scope = 'agent';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'max_workers' AND config.scope = 'agent';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'min_workers' AND config.scope = 'agent';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'max_workers' AND config.scope = 'mgmtworker';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'min_workers' AND config.scope = 'mgmtworker';

UPDATE config SET schema='{"type": "integer", "minimum": 0}' WHERE config.name = 'blueprint_folder_max_files' AND config.scope = 'rest';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'default_page_size' AND config.scope = 'rest';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'failed_logins_before_account_lock' AND config.scope = 'rest';

UPDATE config SET schema='{"type": "integer", "minimum": 1}' WHERE config.name = 'ldap_nested_levels' AND config.scope = 'rest';

UPDATE config SET schema='{"type": "integer", "minimum": -1}' WHERE config.name = 'subgraph_retries' AND config.scope = 'workflow';

UPDATE config SET schema='{"type": "integer", "minimum": -1}' WHERE config.name = 'task_retries' AND config.scope = 'workflow';

UPDATE config SET schema='{"type": "integer", "minimum": -1}' WHERE config.name = 'task_retry_interval' AND config.scope = 'workflow';

ALTER TABLE roles ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE;

UPDATE alembic_version SET version_num='a31cb9e704d3' WHERE alembic_version.version_num = 'b92770a7b6ca';

-- Running upgrade a31cb9e704d3 -> 03ad040e6f78

CREATE TYPE audit_operation AS ENUM ('create', 'update', 'delete');

CREATE TABLE audit_log (
    _storage_id SERIAL NOT NULL, 
    ref_table TEXT NOT NULL, 
    ref_id INTEGER NOT NULL, 
    operation audit_operation NOT NULL, 
    creator_name TEXT, 
    execution_id TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    CONSTRAINT audit_log_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT audit_log_creator_or_user_not_null CHECK (creator_name IS NOT NULL OR execution_id IS NOT NULL)
);

CREATE INDEX audit_log_created_at_idx ON audit_log (created_at);

CREATE INDEX audit_log_ref_idx ON audit_log (ref_table, ref_id);

CREATE INDEX audit_log_ref_table_idx ON audit_log (ref_table);

UPDATE alembic_version SET version_num='03ad040e6f78' WHERE alembic_version.version_num = 'a31cb9e704d3';

-- Running upgrade 03ad040e6f78 -> 8e8314b1d848

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_creator_or_user_not_null;;

CREATE OR REPLACE FUNCTION audit_username() RETURNS TEXT AS $$
        BEGIN
            RETURN current_setting('audit.username');
        EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION audit_execution_id() RETURNS TEXT AS $$
        BEGIN
            RETURN current_setting('audit.execution_id');
        EXCEPTION WHEN syntax_error_or_access_rule_violation THEN
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_storage_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD._storage_id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;


    CREATE OR REPLACE FUNCTION write_audit_log_id() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW.id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD.id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE OR REPLACE FUNCTION write_audit_log_for_events_logs() RETURNS TRIGGER AS $$
        DECLARE
            _table TEXT := TG_ARGV[0]::TEXT;
            _user TEXT := public.audit_username();
            _execution_id TEXT := public.audit_execution_id();
        BEGIN
            IF (_execution_id IS NOT NULL) THEN
                RETURN NULL;
            END IF;
            IF (TG_OP = 'INSERT') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'create', _user, _execution_id, now());
            ELSEIF (TG_OP = 'UPDATE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, NEW._storage_id, 'update', _user, _execution_id, now());
            ELSEIF (TG_OP = 'DELETE') THEN
                INSERT INTO public.audit_log (ref_table, ref_id, operation, creator_name, execution_id, created_at)
                    VALUES (_table, OLD._storage_id, 'delete', _user, _execution_id, now());
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;;

CREATE TRIGGER audit_agents
            AFTER INSERT OR UPDATE OR DELETE ON agents FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('agents');;

CREATE TRIGGER audit_blueprints
            AFTER INSERT OR UPDATE OR DELETE ON blueprints FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('blueprints');;

CREATE TRIGGER audit_blueprints_filters
            AFTER INSERT OR UPDATE OR DELETE ON blueprints_filters FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('blueprints_filters');;

CREATE TRIGGER audit_blueprints_labels
            AFTER INSERT OR UPDATE OR DELETE ON blueprints_labels FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('blueprints_labels');;

CREATE TRIGGER audit_certificates
            AFTER INSERT OR UPDATE OR DELETE ON certificates FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('certificates');;

CREATE TRIGGER audit_deployment_groups
            AFTER INSERT OR UPDATE OR DELETE ON deployment_groups FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployment_groups');;

CREATE TRIGGER audit_deployment_groups_labels
            AFTER INSERT OR UPDATE OR DELETE ON deployment_groups_labels FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('deployment_groups_labels');;

CREATE TRIGGER audit_deployment_labels_dependencies
            AFTER INSERT OR UPDATE OR DELETE ON deployment_labels_dependencies FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployment_labels_dependencies');;

CREATE TRIGGER audit_deployment_modifications
            AFTER INSERT OR UPDATE OR DELETE ON deployment_modifications FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployment_modifications');;

CREATE TRIGGER audit_deployment_update_steps
            AFTER INSERT OR UPDATE OR DELETE ON deployment_update_steps FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployment_update_steps');;

CREATE TRIGGER audit_deployment_updates
            AFTER INSERT OR UPDATE OR DELETE ON deployment_updates FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployment_updates');;

CREATE TRIGGER audit_deployments
            AFTER INSERT OR UPDATE OR DELETE ON deployments FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployments');;

CREATE TRIGGER audit_deployments_filters
            AFTER INSERT OR UPDATE OR DELETE ON deployments_filters FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('deployments_filters');;

CREATE TRIGGER audit_deployments_labels
            AFTER INSERT OR UPDATE OR DELETE ON deployments_labels FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('deployments_labels');;

CREATE TRIGGER audit_execution_groups
            AFTER INSERT OR UPDATE OR DELETE ON execution_groups FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('execution_groups');;

CREATE TRIGGER audit_execution_schedules
            AFTER INSERT OR UPDATE OR DELETE ON execution_schedules FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('execution_schedules');;

CREATE TRIGGER audit_executions
            AFTER INSERT OR UPDATE OR DELETE ON executions FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('executions');;

CREATE TRIGGER audit_groups
            AFTER INSERT OR UPDATE OR DELETE ON groups FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('groups');;

CREATE TRIGGER audit_inter_deployment_dependencies
            AFTER INSERT OR UPDATE OR DELETE ON inter_deployment_dependencies FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('inter_deployment_dependencies');;

CREATE TRIGGER audit_licenses
            AFTER INSERT OR UPDATE OR DELETE ON licenses FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('licenses');;

CREATE TRIGGER audit_maintenance_mode
            AFTER INSERT OR UPDATE OR DELETE ON maintenance_mode FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('maintenance_mode');;

CREATE TRIGGER audit_managers
            AFTER INSERT OR UPDATE OR DELETE ON managers FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('managers');;

CREATE TRIGGER audit_node_instances
            AFTER INSERT OR UPDATE OR DELETE ON node_instances FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('node_instances');;

CREATE TRIGGER audit_nodes
            AFTER INSERT OR UPDATE OR DELETE ON nodes FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('nodes');;

CREATE TRIGGER audit_operations
            AFTER INSERT OR UPDATE OR DELETE ON operations FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('operations');;

CREATE TRIGGER audit_permissions
            AFTER INSERT OR UPDATE OR DELETE ON permissions FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('permissions');;

CREATE TRIGGER audit_plugins
            AFTER INSERT OR UPDATE OR DELETE ON plugins FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('plugins');;

CREATE TRIGGER audit_plugins_states
            AFTER INSERT OR UPDATE OR DELETE ON plugins_states FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('plugins_states');;

CREATE TRIGGER audit_plugins_updates
            AFTER INSERT OR UPDATE OR DELETE ON plugins_updates FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('plugins_updates');;

CREATE TRIGGER audit_roles
            AFTER INSERT OR UPDATE OR DELETE ON roles FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('roles');;

CREATE TRIGGER audit_secrets
            AFTER INSERT OR UPDATE OR DELETE ON secrets FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('secrets');;

CREATE TRIGGER audit_sites
            AFTER INSERT OR UPDATE OR DELETE ON sites FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('sites');;

CREATE TRIGGER audit_snapshots
            AFTER INSERT OR UPDATE OR DELETE ON snapshots FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('snapshots');;

CREATE TRIGGER audit_tasks_graphs
            AFTER INSERT OR UPDATE OR DELETE ON tasks_graphs FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_storage_id('tasks_graphs');;

CREATE TRIGGER audit_tenants
            AFTER INSERT OR UPDATE OR DELETE ON tenants FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('tenants');;

CREATE TRIGGER audit_usage_collector
            AFTER INSERT OR UPDATE OR DELETE ON usage_collector FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('usage_collector');;

CREATE TRIGGER audit_users
            AFTER INSERT OR UPDATE OR DELETE ON users FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_id('users');;

CREATE TRIGGER audit_events
            AFTER INSERT OR UPDATE OR DELETE ON events FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_for_events_logs('events');;

CREATE TRIGGER audit_logs
            AFTER INSERT OR UPDATE OR DELETE ON logs FOR EACH ROW
            EXECUTE PROCEDURE write_audit_log_for_events_logs('logs');;

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('api_service_log_path', '"/var/log/cloudify/rest/cloudify-api-service.log"', NULL, false, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('api_service_log_level', '"INFO"', '{"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]}', true, 'rest');

CREATE INDEX audit_log_creator_name_idx ON audit_log (creator_name);

CREATE INDEX audit_log_execution_id_idx ON audit_log (execution_id);

CREATE OR REPLACE FUNCTION notify_new_audit_log()
        RETURNS TRIGGER AS $$
        BEGIN
            PERFORM pg_notify(
                'audit_log_inserted'::text,
                 row_to_json(NEW)::text
            );
            return NEW;
        END;
    $$ LANGUAGE plpgsql;;

CREATE TRIGGER audit_log_inserted
                  AFTER INSERT ON audit_log FOR EACH ROW
                  EXECUTE PROCEDURE notify_new_audit_log();;

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('max_concurrent_workflows', '20', '{"type": "number", "minimum": 1, "maximum": 1000}', true, 'rest');

ALTER TABLE node_instances ADD COLUMN system_properties TEXT;

ALTER TABLE plugins ADD COLUMN blueprint_labels TEXT;

ALTER TABLE plugins ADD COLUMN labels TEXT;

ALTER TABLE plugins ADD COLUMN resource_tags TEXT;

ALTER TABLE deployments ADD COLUMN resource_tags TEXT;

ALTER TABLE usage_collector ADD COLUMN max_deployments INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN max_blueprints INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN max_users INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN max_tenants INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN total_deployments INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN total_blueprints INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN total_executions INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN total_logins INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE usage_collector ADD COLUMN total_logged_in_users INTEGER DEFAULT '0' NOT NULL;

UPDATE usage_collector SET total_deployments=(SELECT count(1) AS count_1 
FROM deployments), total_blueprints=(SELECT count(1) AS count_2 
FROM blueprints), total_executions=(SELECT count(1) AS count_3 
FROM executions);

CREATE FUNCTION increase_deployments_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_deployments INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_deployments FROM deployments;
            UPDATE usage_collector SET max_deployments = _count_deployments
            WHERE _count_deployments > max_deployments;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_blueprints_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_blueprints INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_blueprints FROM blueprints;
            UPDATE usage_collector SET max_blueprints = _count_blueprints
            WHERE _count_blueprints > max_blueprints;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_users_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_users INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_users FROM users;
            UPDATE usage_collector SET max_users = _count_users
            WHERE _count_users > max_users;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_tenants_max() RETURNS TRIGGER AS $$
        DECLARE
            _count_tenants INTEGER;
        BEGIN
            SELECT COUNT(*) INTO _count_tenants FROM tenants;
            UPDATE usage_collector SET max_tenants = _count_tenants
            WHERE _count_tenants > max_tenants;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_deployments_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector
            SET total_deployments = total_deployments + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_blueprints_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_blueprints = total_blueprints + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_executions_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_executions = total_executions + 1;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE FUNCTION increase_logins_total() RETURNS TRIGGER AS $$
        BEGIN
            UPDATE usage_collector SET total_logins = total_logins + 1;
            IF (OLD.last_login_at IS NULL)
            AND NOT (NEW.last_login_at IS NULL) THEN
                UPDATE usage_collector
                SET total_logged_in_users = total_logged_in_users + 1;
            END IF;
            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER increase_deployments_max
    AFTER INSERT ON deployments FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_deployments_max();

    CREATE TRIGGER increase_blueprints_max
    AFTER INSERT ON blueprints FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_blueprints_max();

    CREATE TRIGGER increase_users_max
    AFTER INSERT ON users FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_users_max();

    CREATE TRIGGER increase_tenants_max
    AFTER INSERT ON tenants FOR EACH STATEMENT
    EXECUTE PROCEDURE increase_tenants_max();

    CREATE TRIGGER increase_deployments_total
    AFTER INSERT ON deployments FOR EACH ROW
    EXECUTE PROCEDURE increase_deployments_total();

    CREATE TRIGGER increase_blueprints_total
    AFTER INSERT ON blueprints FOR EACH ROW
    EXECUTE PROCEDURE increase_blueprints_total();

    CREATE TRIGGER increase_executions_total
    AFTER INSERT ON executions FOR EACH ROW
    EXECUTE PROCEDURE increase_executions_total();

    CREATE TRIGGER increase_logins_total
    AFTER UPDATE OF last_login_at ON users FOR EACH ROW
    EXECUTE PROCEDURE increase_logins_total();;

UPDATE alembic_version SET version_num='8e8314b1d848' WHERE alembic_version.version_num = '03ad040e6f78';

-- Running upgrade 8e8314b1d848 -> 272e61bf5f4a

ALTER TABLE deployment_update_steps ALTER COLUMN entity_id TYPE TEXT[] USING string_to_array(entity_id, ':');

CREATE TABLE tokens (
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    id VARCHAR(10) NOT NULL, 
    secret_hash VARCHAR(255) NOT NULL, 
    description VARCHAR(255), 
    last_used TIMESTAMP WITHOUT TIME ZONE, 
    expiration_date TIMESTAMP WITHOUT TIME ZONE, 
    _user_fk INTEGER NOT NULL, 
    _execution_fk INTEGER, 
    CONSTRAINT tokens_pkey PRIMARY KEY (id), 
    CONSTRAINT tokens__user_fk_fkey FOREIGN KEY(_user_fk) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT tokens__execution_fk_fkey FOREIGN KEY(_execution_fk) REFERENCES executions (_storage_id) ON DELETE CASCADE
);

CREATE INDEX tokens_last_used_idx ON tokens (last_used);

CREATE INDEX tokens__execution_fk_idx ON tokens (_execution_fk);

CREATE INDEX tokens__user_fk_idx ON tokens (_user_fk);

CREATE INDEX tokens_created_at_idx ON tokens (created_at);

ALTER TABLE users DROP COLUMN api_token_key;

ALTER TABLE plugins_updates ADD COLUMN deployments_per_tenant TEXT;

ALTER TABLE plugins_updates ADD COLUMN all_tenants BOOLEAN DEFAULT 'f' NOT NULL;

DROP TRIGGER IF EXISTS audit_usage_collector ON usage_collector;;

ALTER TABLE operations ADD COLUMN manager_name TEXT;

ALTER TABLE operations ADD COLUMN agent_name TEXT;

ALTER TABLE events ADD COLUMN manager_name TEXT;

ALTER TABLE events ADD COLUMN agent_name TEXT;

ALTER TABLE logs ADD COLUMN manager_name TEXT;

ALTER TABLE logs ADD COLUMN agent_name TEXT;

CREATE TYPE log_bundle_status AS ENUM ('created', 'failed', 'creating', 'uploaded');

CREATE TABLE log_bundles (
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    _storage_id SERIAL NOT NULL, 
    id TEXT, 
    visibility visibility_states, 
    status log_bundle_status, 
    error TEXT, 
    _tenant_id INTEGER NOT NULL, 
    _creator_id INTEGER NOT NULL, 
    CONSTRAINT log_bundles_pkey PRIMARY KEY (_storage_id), 
    CONSTRAINT log_bundles__creator_id_fkey FOREIGN KEY(_creator_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT log_bundles__tenant_id_fkey FOREIGN KEY(_tenant_id) REFERENCES tenants (id) ON DELETE CASCADE
);

CREATE INDEX log_bundles__creator_id_idx ON log_bundles (_creator_id);

CREATE INDEX log_bundles__tenant_id_idx ON log_bundles (_tenant_id);

CREATE INDEX log_bundles_created_at_idx ON log_bundles (created_at);

CREATE UNIQUE INDEX log_bundles_id__tenant_id_idx ON log_bundles (id, _tenant_id);

CREATE INDEX log_bundles_id_idx ON log_bundles (id);

CREATE INDEX log_bundles_visibility_idx ON log_bundles (visibility);

ALTER TABLE db_nodes DROP COLUMN monitoring_username;

ALTER TABLE db_nodes DROP COLUMN monitoring_password;

ALTER TABLE managers DROP COLUMN monitoring_password;

ALTER TABLE managers DROP COLUMN monitoring_username;

ALTER TABLE rabbitmq_brokers DROP COLUMN monitoring_password;

ALTER TABLE rabbitmq_brokers DROP COLUMN monitoring_username;

ALTER TABLE config ADD COLUMN admin_only BOOLEAN DEFAULT 'false' NOT NULL;

UPDATE config SET admin_only=true WHERE config.name = 'ldap_username';

UPDATE config SET admin_only=true WHERE config.name = 'ldap_password';

INSERT INTO config (name, value, schema, is_editable, admin_only, scope) VALUES ('log_fetch_username', '""', NULL, true, true, 'rest');

INSERT INTO config (name, value, schema, is_editable, admin_only, scope) VALUES ('log_fetch_password', '""', NULL, true, true, 'rest');

INSERT INTO config (name, value, schema, is_editable, scope) VALUES ('marketplace_api_url', '"https://marketplace.cloudify.co"', '{"type": "string"}', true, 'rest');

ALTER TABLE deployments ADD COLUMN drifted_instances INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE deployments ADD COLUMN unavailable_instances INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE node_instances ADD COLUMN is_status_check_ok BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE node_instances ADD COLUMN has_configuration_drift BOOLEAN DEFAULT 'false' NOT NULL;

ALTER TABLE nodes ADD COLUMN drifted_instances INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE nodes ADD COLUMN unavailable_instances INTEGER DEFAULT '0' NOT NULL;

UPDATE node_instances SET is_status_check_ok = true;;

CREATE OR REPLACE FUNCTION recalc_drift_instance_counts(node_id integer)
RETURNS void AS $$
UPDATE public.nodes n
SET
    drifted_instances = (
        SELECT COUNT(1)
        FROM public.node_instances ni
        WHERE ni._node_fk = n._storage_id
        AND ni.has_configuration_drift
    ),
    unavailable_instances = (
        SELECT COUNT(1)
        FROM public.node_instances ni
        WHERE ni._node_fk = n._storage_id
        AND NOT ni.is_status_check_ok
    )
WHERE n._storage_id = node_id;

UPDATE public.deployments d
SET
    drifted_instances = (
        SELECT SUM(n.drifted_instances)
        FROM public.nodes n
        WHERE n._deployment_fk = d._storage_id
    ),
    unavailable_instances = (
        SELECT SUM(n.unavailable_instances)
        FROM public.nodes n
        WHERE n._deployment_fk = d._storage_id
    )
WHERE d._storage_id = (
    SELECT n._deployment_fk
    FROM public.nodes n
    WHERE n._storage_id = node_id
    LIMIT 1
);
$$ LANGUAGE sql;

CREATE OR REPLACE FUNCTION recalc_drift_instance_counts_insert()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM public.recalc_drift_instance_counts(NEW._node_fk);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION recalc_drift_instance_counts_update()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM public.recalc_drift_instance_counts(OLD._node_fk);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER recalc_drift_instance_counts_insert
AFTER INSERT
ON node_instances
FOR EACH ROW
EXECUTE PROCEDURE recalc_drift_instance_counts_insert();

CREATE TRIGGER recalc_drift_instance_counts_update
AFTER  DELETE
OR UPDATE OF has_configuration_drift, is_status_check_ok
ON node_instances
FOR EACH ROW
EXECUTE PROCEDURE recalc_drift_instance_counts_update();;

UPDATE alembic_version SET version_num='272e61bf5f4a' WHERE alembic_version.version_num = '8e8314b1d848';

COMMIT;

