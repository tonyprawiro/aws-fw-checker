def check_rds(aws_access_key_id, aws_secret_access_key, region_name,
              secgroups_with_0000_0, secgroups_public_ports,
              exclusion_path, alerted_path):
    """Return RDS instances that need to be alerted"""
    import boto3
    import check_lib

    # Create boto3 RDS client
    rds = boto3.client('rds',
                       aws_access_key_id=aws_access_key_id,
                       aws_secret_access_key=aws_secret_access_key,
                       region_name=region_name)

    # Get exclusions and alerted
    exclusions = check_lib.get_exclusions(exclusion_path)
    alerted = check_lib.get_alerted(alerted_path)

    # Get RDS instances
    rds_instances = rds.describe_db_instances()
    databases = []
    for db in rds_instances["DBInstances"]:

        if db["PubliclyAccessible"] and db["DBInstanceStatus"]=="available":

            dbdata = {}
            dbdata["DBInstanceIdentifier"] = db["DBInstanceIdentifier"]
            dbdata["DBName"] = db["DBName"]
            dbdata["Engine"] = db["Engine"]
            dbdata["Endpoint"] = "%s:%d" % (db["Endpoint"]["Address"], db["Endpoint"]["Port"])
            dbdata["Ports"] = []

            for grp in db["VpcSecurityGroups"]:

                if grp["VpcSecurityGroupId"] in secgroups_with_0000_0:  # If the security group contains 0.0.0.0/0

                    for ps in secgroups_public_ports[grp["VpcSecurityGroupId"]]:
                        # Check the ports in this security group

                        secgroup_port = secgroups_public_ports[grp["VpcSecurityGroupId"]]

                        if " to " in secgroup_port:
                            from_port, to_port = secgroup_port.split(" to ", 2)
                        else:
                            from_port = secgroup_port
                            to_port = secgroup_port

                        if from_port <= db["Endpoint"]["Port"] <= to_port:
                            dbdata["Ports"].append(ps)

            if len(dbdata["Ports"]) > 0:  # There are exposed ports not in exclusion list

                # Has it been alerted before?
                object_hash = check_lib.cache_get_key(dbdata)
                if object_hash not in alerted:
                    alerted.append(object_hash)
                    databases.append(dbdata)

    # Record back alerted list
    check_lib.record_alerted(alerted_path, alerted)

    return databases
