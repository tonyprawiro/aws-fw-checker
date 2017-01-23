# aws-fw-checker

A simple script to perform a security group check against your own (AWS) EC2 and RDS instances by parsing and verifying security group rules.

The script will check only running instances which are publicly-accessible.

For instance, having a public IP address, or having `PubliclyAccessible` attribute set to True for RDS.

## How to run

```
$ FWCHECK_ACCOUNT_NAME=any-string \
  AWS_ACCESS_KEY_ID=AKIA123123123123123123123 \
  AWS_SECRET_ACCESS_KEY="1232341231233423132353452412134235245243" \
  AWS_REGION_NAME="ap-southeast-1" \
  TELEGRAM_BOT_TOKEN="123123123:abcdef123123123123123123123123123123" \
  TELEGRAM_CHATGROUP_ID="-123123123123" \
  python check.py
```

Example output:

```
...
Name: My Machine Name (i-abc123def)
IP address: 54.123.123.123
Port(s): 80, 443

...
```

## Wrap this script

This script is meant to be wrapped in another process, such as a shell script, so that checks can be run as a batch with different API keys. This means you could run checks on multiple AWS accounts with only a single set of script and wrapper.

# Improvements

- Need to check ELBs too
