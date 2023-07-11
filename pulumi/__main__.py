import pulumi
import pulumi_hcloud as hcloud
import os
import requests
import yaml

def get_snapshot_ids(snapshot_name):
    token   = os.getenv('HCLOUD_TOKEN')
    headers = {
        'Authorization': 'Bearer ' + token,
    }

    response    = requests.get('https://api.hetzner.cloud/v1/images?type=snapshot', headers=headers)
    data        = response.json()
    
    for image in data['images']:
        if image['name'] == snapshot_name:
            return image['id']
    return None

def create_network(name, cidrblock):
    return hcloud.Network(name, ip_range=cidrblock)


def create_subnet(network_id, zone, name, cidrblock):
    return hcloud.NetworkSubnet(network_id=network_id, network_zone=zone, type='server', resource_name=name, ip_range=cidrblock)


def create_servers(config, network):
    master_instances = []
    worker_instances = []

    for master in config['topology']['hcloud_master_server']:
        master_instances.append(hcloud.Server(master['name'],
                                    server_type=master['type'],
                                    image=master['image'],
                                    ssh_keys=master['ssh-key'],
                                    networks=[hcloud.ServerNetworkArgs(network_id=network.id)],
                                    labels={ 'group':'master' })
        )

    for worker in config['topology']['hcloud_worker_server']:
        worker_instances.append(hcloud.Server(worker['name'],
                                    server_type=worker['type'],
                                    ssh_keys=worker['ssh-key'],
                                    networks=[hcloud.ServerNetworkArgs(network_id=network.id)],
                                    image=worker['image'],
                                    labels={ 'group':'worker' })
        )

if __name__ == '__main__':
    config          = pulumi.Config()
    hcloud_config   = yaml.safe_load( os.environ.get('HCLOUD_CONFIG') )
    network         = create_network(hcloud_config['network']['name'], hcloud_config['network']['cidrblock'])
    create_subnet(network_id=network.id, 
                  zone=hcloud_config['network']['subnet']['zone'], 
                  name=hcloud_config['network']['subnet']['name'], 
                  cidrblock=hcloud_config['network']['subnet']['cidrblock']
    )
    create_servers(hcloud_config, network)