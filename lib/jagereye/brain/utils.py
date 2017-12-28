import json


def jsonify(s, encoding=None):
    """Deserialize a str/bytes object, containing a JSON document, to
    a dict object.

    XXX: This wrapper is used to enforce the JSON standard which specified
         key or value should be in double quotes, however, this wrapper would
         cause side-effect when a value containing a single quote in it, e.g.
         can't, will also be replace with a double quotes even it's valid.
         We should remove this wrapper in the future and use testcases to prevent
         non-standard JSON format object being passing around.

    Args:
        s: a str/bytes object

    Returns:
        a dict object
    """
    if type(s) is bytes:
        string = s.decode()
    else:
        string = s
    return json.loads(string.replace("'", '"'), encoding=encoding)


def jsondumps(obj):
    """Serialize obj to JSON formatted str.

    Args:
        obj: a dict object

    Returns:
        a string object
    """
    return json.dumps(obj)
