def get_admin_user():
    return [
        {
            'username': 'admin',
            'password': 'admin',
            'roles': ['administrator']
        }
    ]


def get_admin_role():
    return [
        {
            'name': 'administrator',
            'description': 'The administrator role can access any '
                           'endpoint, and call any method',
            'allow': {'*': ['*']}
         }
    ]


def get_test_users():
    test_users = [
        {
            'username': 'alice',
            'password': 'alice_password',
            'roles': ['administrator']
        },
        {
            'username': 'bob',
            'password': 'bob_password',
            'roles': ['deployer']
        },
        {
            'username': 'clair',
            'password': 'clair_password',
            'roles': ['viewer']
        },
        {
            'username': 'dave',
            'password': 'dave_password',
            'roles': []
        }
    ]
    return test_users


def get_test_roles():
    return [
        {
            'name': 'administrator',
            'description': 'The administrator role can access any '
                           'endpoint, and call any method',
            'allow': {'*': ['*']}
         },
        {
            'name': 'deployer',
            'description': 'The deployer role can access any '
                           'endpoint, and call any method except DELETE',
            'allow': {'*': ['*']},
            'deny': {'/api/v2.1/maintenance/*': ['POST'], '*': ['DELETE']}
        },
        {
            'name': 'viewer',
            'description': 'The viewer role can can access any '
                           'endpoint, but only call the GET method',
            'allow': {'*': ['GET']},
            'deny': {
                '/api/v1/blueprints/blueprint_2': ['*'],
                '/api/v2/blueprints/blueprint_2': ['*'],
                '/api/v2.1/blueprints/blueprint_2': ['*']
            }
        }
    ]
