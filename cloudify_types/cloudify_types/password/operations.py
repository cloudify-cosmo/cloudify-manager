from secrets import choice, SystemRandom
from string import ascii_lowercase, ascii_uppercase, digits, punctuation

from cloudify import manager, ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
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

    if not secret_name:
        secret_name = f'pswd_{ctx.deployment.id}_{ctx.node.id}'

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
    ctx.instance.runtime_properties['secret_name'] = secret_name
    ctx.logger.info('Created password. Secret name: %s', secret_name)
    return True


@operation(resumable=True)
@errors_nonrecoverable
def delete(**kwargs):
    secret_name = ctx.instance.runtime_properties.get('secret_name')
    remove_secret = \
        get_desired_operation_input('uninstall_removes_secret', kwargs)
    if remove_secret:
        _delete_secrets(manager.get_rest_client(), [secret_name])
    return True


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
