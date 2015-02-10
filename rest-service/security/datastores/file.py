from abstract_datastore import AbstractDatastore


# This is supposedly read from a file:
credentials = {
    'user1': 'pass1',
    'user2:': 'pass2',
    'user3': 'pass3'
}


class FileDatastore(AbstractDatastore):

    def get_user(self, identifier):
        user = None

        for username, password in credentials:
            if username == identifier:
                user = {'name': username,
                        'email': username + '@cloudify.org',
                        'password': password}
                break

        return user
