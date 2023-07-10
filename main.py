import argparse
import yaml
import asyncio
import os
import sys
import subprocess
import requests
import jinja2


def setup() -> None:
    # Install packer plugin for hcloud
    cmd = ["packer", "plugins", "install", "github.com/hashicorp/hcloud"]
    subprocess.run(cmd)


async def run_packer_command(command: list, env: dict) -> None:
    process = await asyncio.create_subprocess_exec(*command, env=env)
    await process.wait()


async def create_images(conf: dict) -> None:
    k3s_build   = ['packer', 'build', 'images/k3s.json']
    tasks       = []
    for k, v in conf['image_base'].items():
        if v == True:
            env = os.environ | {
                'HCLOUD_LOCATION': conf['hcloud_location'],
                'HCLOUD_ARCHITECTURE': 'arm' if k == 'arm' else 'x86',
                'HCLOUD_TYPE_SERVER': 'cax11' if k == 'arm' else 'cap11'
        }
            
            tasks.append(run_packer_command(k3s_build, env))
    await asyncio.gather(*tasks)
    print("Packer commands executed successfully.")


def create_infrastructure(config:dict, state:str) -> None:
    print("Creating infrastructure...")
    cmd = ["pulumi", state]

    subprocess.run(cmd, cwd='pulumi', env=os.environ | {'HCLOUD_CONFIG':yaml.dump(config)})


def ipv4_by_label(label, value):
    token = os.environ.get('HCLOUD_TOKEN')
    headers = {
        'Authorization': 'Bearer ' + token,
    }

    response = requests.get('https://api.hetzner.cloud/v1/servers', headers=headers)
    data = response.json()

    # Iterate over the servers and check their labels
    server_info = []
    for server in data['servers']:
        labels = server['labels']
        if labels.get(label) == value:
            server_info.append({"name": server['name'], "ip": server['public_net']['ipv4']['ip']})

    # Now ipv4_addresses contains the IPv4 addresses of all servers with the desired label
    return server_info

def setup_k3s() -> None:
    masters = ipv4_by_label('group', 'master')
    workers = ipv4_by_label('group', 'worker')

    with open('ansible/inventory.j2') as t:
        template = jinja2.Template(t.read())

    with open('ansible/inventory', 'w') as fo:
        fo.write(template.render({'masters': masters, 'workers': workers}))

def parameters() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config-file', 
                        required=True, 
                        help='Path to the configuration file'
    )
    parser.add_argument('-p', '--profile', 
                        required=True, 
                        help='Profile to be used'
    )
    parser.add_argument('--state', 
                        required=True, 
                        default='up',
                        help='Profile to be used'
    )
    parser.add_argument('--create-images', 
                        action='store_true', 
                        help='Indicates that the base images has to be created with Packer'
    )
    args = parser.parse_args()

    if not args.config_file:
        print('Configuration file path not provided. Use --config-file <path/to/config.yaml>')
        sys.exit(1)
    
    if not args.profile:
        print('profile not provided. Use --profile <laboratory|develop|production>')
        sys.exit(1)
        
    return args


if __name__ == '__main__':
    args = parameters()

    with open(args.config_file) as conf:
        config = yaml.safe_load(conf.read())[args.profile]

    # Install requirements for the app
    setup()

    if args.create_images:
        loop                = asyncio.get_event_loop()
        create_images_task  = loop.create_task(create_images(config))
        loop.run_until_complete(create_images_task)
        loop.close()

        # Wait for create_images() coroutine to complete
        if create_images_task.done():
            create_infrastructure(config=config, state=args.state)
            setup_k3s()

    elif not args.create_images:
        create_infrastructure(config, state=args.state)
    setup_k3s()