import requests
LOCAL_QUERY_URL = 'http://127.0.0.1:9090/monitoring/api/v1/query'


def query(query_string, logger, timeout=None):
    query_url = LOCAL_QUERY_URL
    url_with_query_string = (
        query_url + '?query=' + requests.utils.quote(query_string)
    )
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


def _format_prometheus_response(response):
    if response.status_code == requests.codes.ok and 'data' in response.json():
        response_data = response.json()['data']
        if 'result' in response_data and 'resultType' in response_data:
            return response_data['result']
    return None
