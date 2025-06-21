export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv activate napalm-env
cd /code/lldp-network-discovery
python net_discovery.py 192.168.122.201 credentials.yaml 3 --debug

Clone ntc-templates repo locally at ~/ntc-templates (or update path in script).
git clone https://github.com/networktocode/ntc-templates.git

git clone https://github.com/networktocode/ntc-templates.git ~/ntc-templates


python net_discovery.py <seed_ip> <credentials.yaml> <depth> [--debug]
python net_discovery.py 192.168.100.121 credentials.yaml 3 --debug

# Output

## Terminal
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