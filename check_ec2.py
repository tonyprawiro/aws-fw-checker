def get_instance_tag_value(arr, tag_name = "Name"):
    """Return instance tag value"""
    result = ""
    try:
        for member in arr:
            if member["Key"] == "Name":
                result = member["Value"]
    except:
        pass
    return result


def get_secgroups(aws_access_key_id, aws_secret_access_key, region_name):
    import boto3
    """Get security groups"""

    # Create boto3 EC2 client
    ec2 = boto3.client('ec2',
                       aws_access_key_id=aws_access_key_id,
                       aws_secret_access_key=aws_secret_access_key,
                       region_name=region_name)

    secgroups = ec2.describe_security_groups()
    secgroups_with_0000_0 = []  # Security group IDs that contains 0.0.0.0/0
    secgroups_public_ports = {}  # Ports
    for secgroup in secgroups["SecurityGroups"]:
        calc = []
        for ingress in secgroup["IpPermissions"]:
            if ingress["IpProtocol"] == "tcp":
                for ip_range in ingress["IpRanges"]:
                    cidr = ""
                    try:
                        cidr = ip_range["CidrIp"]
                    except:
                        pass
                    if cidr == "0.0.0.0/0":
                        s = "%s" % ingress["FromPort"]
                        if ingress["ToPort"] != ingress["FromPort"]:
                            s = "%s to %s" % (ingress["FromPort"], ingress["ToPort"])
                        calc.append(s)
                        secgroups_with_0000_0.append(secgroup["GroupId"])
        secgroups_public_ports[secgroup["GroupId"]] = calc

    return secgroups, secgroups_with_0000_0, secgroups_public_ports


def check_ec2(aws_access_key_id, aws_secret_access_key, region_name,
              secgroups_with_0000_0, secgroups_public_ports,
              exclusion_path, alerted_path):
    """Return machines that need to be alerted"""
    import boto3
    import check_lib

    # Create boto3 EC2 client
    ec2 = boto3.client('ec2',
                       aws_access_key_id=aws_access_key_id,
                       aws_secret_access_key=aws_secret_access_key,
                       region_name=region_name)

    # Get exclusions and alerted
    exclusions = check_lib.get_exclusions(exclusion_path)
    alerted = check_lib.get_alerted(alerted_path)

    # Get machines
    instances = ec2.describe_instances(MaxResults=1000)  # Get all machines.. too lazy to work on the pagination
    machines = []
    for res in instances["Reservations"]:

        for inst in res["Instances"]:

            """inst is a single instance"""
            public_ip = ""
            try:
                public_ip = inst["PublicIpAddress"]
            except:
                pass

            if public_ip != "" and inst["State"]["Code"] == 16:  # Only process if machine is running with public IP

                # Gather basic information about the machine
                machine = {}
                machine["State"] = inst["State"]["Name"]
                machine["InstanceId"] = inst["InstanceId"]
                machine["Name"] = get_instance_tag_value(arr=inst["Tags"], tag_name="Name")
                if machine["Name"] == "":
                    machine["Name"] = inst["InstanceId"]
                machine["IpAddress"] = public_ip
                machine["Ports"] = []

                # Iterate all security groups associated with the machine
                for grp in inst["SecurityGroups"]:

                    if grp["GroupId"] in secgroups_with_0000_0:
                        # If the security group contains 0.0.0.0/0 (in scrutiny)

                        for ps in secgroups_public_ports[grp["GroupId"]]:  # Check the ports in this security group

                            if ps not in machine["Ports"]:  # If this port has not been noted before

                                # If there is exclusion for this machine, and the port is not in the list,
                                # then note this port
                                # If there is no exclusion for this machine, then note this port
                                try:
                                    if ps not in exclusions[inst["InstanceId"]]:
                                        machine["Ports"].append(ps)
                                except:
                                    machine["Ports"].append(ps)

                if len(machine["Ports"]) > 0:  # There are some exposed ports and not in exclusion list

                    # Has it been alerted before?
                    object_hash = check_lib.cache_get_key(machine)
                    if object_hash not in alerted:
                        alerted.append(object_hash)
                        machines.append(machine)

    # Record back alerted list
    check_lib.record_alerted(alerted_path, alerted)

    return machines
