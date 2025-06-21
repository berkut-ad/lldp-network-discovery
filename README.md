# Setup Python Virtual Environment

``` bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate lldp-env
```

# Clone repository to your preferred directory and download ntc-templates

```bash
cd /code/lldp-network-discovery
Clone ntc-templates repo locally at ~/ntc-templates (or update path in script).
git clone https://github.com/networktocode/ntc-templates.git
git clone https://github.com/networktocode/ntc-templates.git ~/ntc-templates
```

# Execute 

Format is python net_discovery.py <SEED_IP> <Credentials file> <discovery depth> --debug
 - The Discovery Depth is how many devices from the seed device/ip will the script do the discovery. eg Seed Device ---> Device A1 ---> Device A2 ---> Device A3 ---> Device A4.
    - With Discovery Depth of 3 all devices upto A3 will be discovered.
    - With Discovery Depth of 4 all devices upto A4 will be discovered.

``` bash
python net_discovery.py 192.168.122.201 credentials.yaml 3 --debug
```

- To enable DEBUG flag

``` bash
python net_discovery.py <seed_ip> <credentials.yaml> <depth> [--debug]
python net_discovery.py 192.168.100.121 credentials.yaml 3 --debug
```

# Output

## Terminal

```bash
Discovered devices:
+-----------------+-------------+----------+
|       ip        | device_type | hostname |
+-----------------+-------------+----------+
| 192.168.122.201 | arista_eos  | veos-b1  |
| 192.168.122.203 | arista_eos  | veos-a1  |
| 192.168.122.204 | arista_eos  | veos-a2  |
| 192.168.122.202 | arista_eos  | veos-b2  |
+-----------------+-------------+----------+

## File discovered_devices.csv 
ip,device_type,hostname
192.168.122.201,arista_eos,veos-b1
192.168.122.203,arista_eos,veos-a1
192.168.122.204,arista_eos,veos-a2
```