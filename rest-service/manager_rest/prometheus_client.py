import typing
import requests

from manager_rest import config


def query(query_string: str, logger, timeout=None) -> typing.List[dict]:
    query_url = '{}/monitoring/api/v1/query'.format(
        config.instance.prometheus_url,
    )
    url_with_query_string = \
        query_url + '?query=' + requests.compat.quote(query_string)
    params = {'query': query_string}
    try:
        r = requests.get(query_url,
                         params=params,
                         timeout=timeout)
    except Exception as err:
        logger.error(
            "Error retrieving prometheus results from '%s': (%s) %s",
            url_with_query_string,
            type(err),
            err,
        )
        result = []
    else:
        result = _format_prometheus_response(r) or []

        if not result:
            logger.error(
                "Could not get prometheus results from '%s'. "
                'Response code %s.',
                url_with_query_string,
                r.status_code,
            )
    return result


def _format_prometheus_response(
        response: requests.Response) -> typing.Optional[list]:
    if response.status_code == requests.codes.ok and 'data' in response.json():
        response_data = response.json()['data']
        if 'result' in response_data and 'resultType' in response_data:
            return response_data['result']
    return None
