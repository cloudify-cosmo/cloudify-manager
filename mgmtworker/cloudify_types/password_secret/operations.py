from secrets import choice, SystemRandom
from string import ascii_lowercase, ascii_uppercase, digits, punctuation

from cloudify import manager, ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_types.utils import (_set_secrets,
                                  _delete_secrets,
                                  errors_nonrecoverable,
                                  get_desired_operation_input)


@operation(resumable=True)
@errors_nonrecoverable
def create(**kwargs):
    length = get_desired_operation_input('length', kwargs)
    min_uppercase = get_desired_operation_input('uppercase', kwargs)
    min_lowercase = get_desired_operation_input('lowercase', kwargs)
    min_digits = get_desired_operation_input('digits', kwargs)
    min_symbols = get_desired_operation_input('symbols', kwargs)
    secret_name = get_desired_operation_input('secret_name', kwargs)
    use_secret_if_exists = get_desired_operation_input('use_secret_if_exists',
                                                       kwargs)
    if use_secret_if_exists:
        if not secret_name:
            raise NonRecoverableError(
                "Can't enable `use_secret_if_exists` property without "
                "providing a secret_name")
        else:
            password = _get_secret(secret_name)
            if password:
                ctx.instance.runtime_properties['secret_name'] = secret_name
                ctx.instance.runtime_properties['password'] = \
                    {"get_secret": secret_name}
                ctx.logger.info('Using existing password from secret `%s`',
                                secret_name)
                return True

    # For resumability
    if ctx.instance.runtime_properties.get('password'):
        return True

    if not secret_name:
        secret_name = f'ps_{ctx.deployment.id}_{ctx.instance.id}'

    password = []
    required_length = 0
    symbols = ' ' + punctuation

    alphabet = \
        (ascii_uppercase if min_uppercase >= 0 else '') + \
        (ascii_lowercase if min_lowercase >= 0 else '') + \
        (digits if min_digits >= 0 else '') + \
        (symbols if min_symbols >= 0 else '')

    if min_uppercase > 0:
        required_length += min_uppercase
        for _ in range(min_uppercase):
            password.append(choice(ascii_uppercase))
    if min_lowercase > 0:
        required_length += min_lowercase
        for _ in range(min_lowercase):
            password.append(choice(ascii_lowercase))
    if min_digits > 0:
        required_length += min_digits
        for _ in range(min_digits):
            password.append(choice(digits))
    if min_symbols > 0:
        required_length += min_symbols
        for _ in range(min_symbols):
            password.append(choice(symbols))
    for _ in range(length - required_length):
        password.append(choice(alphabet))

    SystemRandom().shuffle(password)
    password = ''.join(password)

    _set_secrets(manager.get_rest_client(), {secret_name: password})
    ctx.instance.runtime_properties['password'] = {"get_secret": secret_name}
    ctx.instance.runtime_properties['secret_name'] = secret_name
    ctx.logger.info('Created password secret.')
    return True


@operation(resumable=True)
@errors_nonrecoverable
def delete(**kwargs):
    secret_name = ctx.instance.runtime_properties.get('secret_name')
    _delete_secrets(manager.get_rest_client(), [secret_name])
    del ctx.instance.runtime_properties['password']
    del ctx.instance.runtime_properties['secret_name']


@errors_nonrecoverable
def creation_validation(**kwargs):
    length = get_desired_operation_input('length', kwargs)
    min_uppercase = get_desired_operation_input('uppercase', kwargs)
    min_lowercase = get_desired_operation_input('lowercase', kwargs)
    min_digits = get_desired_operation_input('digits', kwargs)
    min_symbols = get_desired_operation_input('symbols', kwargs)

    if length < 6:
        raise NonRecoverableError(
            'Password length is required to be at least 6 characters')

    if (min_uppercase < -1 or min_lowercase < -1 or min_digits < -1 or
            min_symbols < -1):
        raise NonRecoverableError(
            'Illegal character group length provided: expecting an integer '
            'greater than 0, or -1 for not using this character group')

    if (min_uppercase == -1 and min_lowercase == -1 and min_digits == -1 and
            min_symbols == -1):
        raise NonRecoverableError(
            'Could not satisfy password requirements: at least one character '
            'group should be used')

    if min_uppercase + min_lowercase + min_digits + min_symbols > length:
        raise NonRecoverableError(
            'Could not satisfy password requirements: lengths of required '
            'character groups is larger than the password length')
    return True


def _get_secret(key):
    try:
        return manager.get_rest_client().secrets.get(key)
    except CloudifyClientError:
        return
