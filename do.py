import boto3
import os
import json
import sys
import base64
import textwrap
import subprocess

# define common ports here, add as needed
common_ports = [
    # privileged
    21, 22, 23, 25, 80, 110, 139, 389, 443, 445,
    # pptp
    1723,
    # rdp
    3389,
    # extra app servers
    8080, 8000, 3000, 5666, 5900,
    # databases (sql, oracle, mysql, postgres, mongo)
    1433, 1521, 3306, 5432, 27017, 27018, 27019, 28017]

# define machine image for DO
digital_ocean_machine_image_id = 17384153


def file_get_contents(filename):
    '''Get content of a file, hopefully a small file!'''
    with open(filename) as f:
        return f.read()

def default(obj):
    '''JSON serializer'''
    import calendar, datetime

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(
            calendar.timegm(obj.timetuple()) * 1000 +
            obj.microsecond / 1000
        )
        return millis
    raise TypeError('Not sure how to serialize %s' % (obj,))

# Return a member of arr where member's field == value
def lookup(arr, field, value):
    result = None
    try:
        for member in arr:
            if member[field] == value:
                result = member
    except:
        pass
    return result

# Add indent to textwrap module
try:
    import textwrap
    textwrap.indent
except AttributeError:  # undefined function (wasn't added until Python 3.3)
    def indent(text, amount, ch=' '):
        padding = amount * ch
        return ''.join(padding+line for line in text.splitlines(True))
else:
    def indent(text, amount, ch=' '):
        return textwrap.indent(text, amount * ch)

# retrieve credentials from environment variable
try:
    AWS_ACCESS_KEY_ID = os.environ["FWCHECK_AWS_ACCESS_KEY_ID"]
    AWS_SECRET_KEY = os.environ["FWCHECK_SECRET_KEY"]
    AWS_REGION = os.environ["FWCHECK_REGION"]
    DO_TOKEN = os.environ["FWCHECK_DO_TOKEN"]
except:
    print "Usage: FWCHECK_AWS_ACCESS_KEY_ID=XXXXX \\"
    print "       FWCHECK_SECRET_KEY=XXXXX \\"
    print "       FWCHECK_REGION=XXXXX \\"
    print "       FWCHECK_DO_TOKEN=XXXXX \\"
    print "       do.py"
    exit(2)

# Create boto3 EC2 client
ec2 = boto3.client('ec2', 
                   aws_access_key_id=AWS_ACCESS_KEY_ID,
                   aws_secret_access_key=AWS_SECRET_KEY,
                   region_name=AWS_REGION)

scan_ports = common_ports

# Get security groups and cache group/ports information
secgroups = ec2.describe_security_groups()
secgrpports = {}
for secgroup in secgroups["SecurityGroups"]:
    ports = []
    for ingress in secgroup["IpPermissions"]:
        if ingress["IpProtocol"] == "-1":
            contains_all_traffic = True
        if ingress["IpProtocol"] == "tcp":
            from_port = ingress["FromPort"]
            to_port = ingress["ToPort"]
            if to_port - from_port != 65535:
                for p in range(from_port, to_port+1):
                    ports.append(p)
                    if p not in scan_ports:
                        scan_ports.append(p)
    secgrpports[secgroup["GroupId"]] = ports

# Get machines
instances = ec2.describe_instances(MaxResults = 1000)
result = {}
machines = []
for res in instances["Reservations"]:
    for inst in res["Instances"]:
        public_ip = ""
        try:
            public_ip = inst["PublicIpAddress"]
        except:
            pass
        if public_ip != "":
            machine = {}
            machine["IpAddress"] = public_ip
            machine["Ports"] = [] #common_ports
            for grp in inst["SecurityGroups"]:
                machine["Ports"].extend(secgrpports[grp["GroupId"]])
            machines.append(machine)

result = machines

# Encode the result properly
result_encoded = "\n".join(
    textwrap.wrap(
        base64.standard_b64encode(
            json.dumps(result, default=default)
        )
    )
)

result_encoded_indented = indent(result_encoded, 4)

# Generate a new RSA keypair
os.remove("fwcheck")
os.remove("fwcheck.pub")
subprocess.call("/usr/bin/ssh-keygen -q -t rsa -f fwcheck -N \"\"", shell=True)

# Get public key content
ssh_public_key = file_get_contents('fwcheck.pub')

# user data
user_data = """
#cloud-config

package_upgrade: true

users:
  - name: fwchecker
    shell: /bin/bash
    ssh-authorized-keys:
      - %s

packages:
  - telnet
  - wget
  - git
  - curl
  - vim

write_files:
  - encoding: b64
    content: !!binary |
%s
    path: /root/data.json

runcmd:
  - 
""" % (
    ssh_public_key,
    result_encoded_indented
)

'''
Sample command to test TCP port open, CentOS 7 (ncat 6.4)
nc -n -w5 220.255.6.55 5000 </dev/null
'''
print user_data
