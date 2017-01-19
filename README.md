# aws-fw-checker

A simple script to perform a firewall check against your own (AWS) machines by scanning security group rules.

## How to run

```
$ AWS_ACCESS_KEY_ID=AKIA123123123123123123123 \
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

# Improvements

- Need to check ELB and RDS, too
