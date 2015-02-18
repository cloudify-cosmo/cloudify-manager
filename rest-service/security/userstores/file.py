from abstract_userstore import AbstractUserstore
from security.models import User, Role

USERNAME = 'username'
PASSWORD = 'password'
EMAIL = 'email'
ROLES = 'roles'

# TODO read this from a file:
user_repo = [
    {USERNAME: 'user1', PASSWORD: 'pass1', EMAIL: 'user1@cloudify.org', ROLES: ('admin', 'viewer')},
    {USERNAME: 'user2', PASSWORD: 'pass2', EMAIL: 'user2@cloudify.org', ROLES: ('admin',)},
    {USERNAME: 'user3', PASSWORD: 'pass3', EMAIL: 'user3@cloudify.org', ROLES: ('viewer',)},
    {USERNAME: 'user4', PASSWORD: 'pass4', EMAIL: 'user4@cloudify.org', ROLES: ()},
]


class FileUserstore(AbstractUserstore):
    _identifying_attribute = USERNAME

    def __init__(self, *args, **kwargs):
        pass

    def get_user(self, unique_identifier):
        user_obj = None
        print '***** getting user with identifier: ', unique_identifier
        if not unique_identifier:
            raise Exception('unique_identifier is missing or empty, '
                            'unable to get a user object')

        for user_entry in user_repo:
            print '***** user identifier value: ', user_entry[FileUserstore._identifying_attribute]
            if user_entry[FileUserstore._identifying_attribute] == unique_identifier:
                print '***** found user!'
                # a matching user was found, return as a User object
                user_obj = FileUserstore._create_user_object(user_entry)
                break

        return user_obj

    @staticmethod
    def _create_user_object(user_dict):

        roles = []
        for role_name in user_dict[ROLES]:
            roles.append(Role(role_name))

        return User(user_dict[USERNAME], user_dict[PASSWORD],
                    user_dict[EMAIL], roles, active=True)
