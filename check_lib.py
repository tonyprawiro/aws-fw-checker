def default_json_serializer(obj):
    """Default JSON serializer."""
    import calendar, datetime

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(
            calendar.timegm(obj.timetuple()) * 1000 +
            obj.microsecond / 1000
        )
        return millis
    raise TypeError('Not sure how to serialize %s' % (obj))


def get_exclusions(exclusion_path):
    """Get exclusions"""
    import json

    # Load exclusion list, exclude.<ACCOUNT-NAME>.json, which must be in the same directory as this file
    # the exclusion works both for EC2 and RDS instances
    # example:
    # {
    #     "i-abc12345": [
    #         "80",
    #         "443"
    #     ],
    #     "i-def54321": [
    #         "8443"
    #     ],
    #     "rds-instance-name1",
    #     "rds-instance-name2"
    # }

    with open(exclusion_path) as f:
        exclusion_json = f.read()
    exclusions = json.loads(exclusion_json)

    return exclusions


def get_alerted(alerted_path):
    """Get alerted"""
    import json

    # Load alerted list, alerted.<ACCOUNT-NAME>.json, which must be in the same directory as this file
    # The alert list serves to mark the alerts, making sure that the same alert won't go off more than once
    # I'd recommend that the alert list is cleared regularly, just in case it is not followed up yet after some time
    # Alert item is serialized for optimization, no point editing it manually. So the format isn't explained here.
    # Note that if the structure of the item is changed, the alerted list will need to be cleared as the hash will
    # also be different even if the instance IDs and ports are the same

    with open(alerted_path) as f:
        alerted_json = f.read()
    alerted = json.loads(alerted_json)

    return alerted


def cache_get_key(*args):
    """Generate a hash of an object"""
    return hash(str(args))


def record_alerted(alerted_path, alerted):
    """Record back alerted list"""
    import json

    with open(alerted_path, "w") as f:
        f.write(json.dumps(alerted))
    return True
