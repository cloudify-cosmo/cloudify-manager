import requests
QUERY_URL_TEMPLATE = 'https://{address}:8009/monitoring/api/v1/query'


def query(address, query_string, logger, auth=None, ca_path=None,
          timeout=None):
    query_url = QUERY_URL_TEMPLATE.format(address=address)
    url_with_query_string = (
        query_url + '?query=' + requests.utils.quote(query_string)
    )
    params = {'query': query_string}
    try:
        r = requests.get(query_url,
                         params=params,
                         auth=auth,
                         verify=ca_path if ca_path else True,
                         timeout=timeout)
    except Exception as err:
        logger.error(
            "Error retrieving prometheus results from '%s' with ca '%s': "
            "(%s) %s",
            url_with_query_string,
            ca_path,
            type(err),
            err,
        )
        result = []
    else:
        result = _format_prometheus_response(r) or []

        if not result:
            logger.error(
                "Could not get prometheus results from '%s' with ca '%s'. "
                'Response code %s.',
                url_with_query_string,
                ca_path,
                r.status_code,
            )
    return result


def _format_prometheus_response(response):
    if response.status_code == requests.codes.ok and 'data' in response.json():
        response_data = response.json()['data']
        if 'result' in response_data and 'resultType' in response_data:
            return response_data['result']
    return None
