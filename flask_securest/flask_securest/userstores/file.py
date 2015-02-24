from flask.ext.securest.userstores.abstract_userstore import AbstractUserstore
from flask.ext.securest.models import User, Role

USERNAME = 'username'
PASSWORD = 'password'
EMAIL = 'email'
ROLES = 'roles'

# TODO read this from a file:
user_repo = [
    {USERNAME: 'user1', PASSWORD: 'pass1', EMAIL: 'user1@cloudify.org',
     ROLES: ('admin', 'viewer')},
    {USERNAME: 'user2', PASSWORD: 'pass2', EMAIL: 'user2@cloudify.org',
     ROLES: ('admin',)},
    {USERNAME: 'user3', PASSWORD: 'pass3', EMAIL: 'user3@cloudify.org',
     ROLES: ('viewer',)},
    {USERNAME: 'user4', PASSWORD: 'pass4', EMAIL: 'user4@cloudify.org',
     ROLES: ()},
]


class FileUserstore(AbstractUserstore):

    def __init__(self):
        print '***** INITING class FileUserstore with no args'
        self._identifying_attribute = None

    @property
    def identifying_attribute(self):
        return self._identifying_attribute

    @identifying_attribute.setter
    def identifying_attribute(self, identifying_attribute):
        self._identifying_attribute = identifying_attribute

    def get_user(self, user_identifier):
        user_obj = None

        print '***** getting user where {0} = {1}'\
            .format(self._identifying_attribute, user_identifier)

        if not user_identifier:
            raise Exception('user identifier is missing or empty, '
                            'unable to get a user object')

        for user_entry in user_repo:
            print '***** user identifier value: ', \
                user_entry.get(self._identifying_attribute)
            if user_entry.get(self._identifying_attribute) == user_identifier:
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
