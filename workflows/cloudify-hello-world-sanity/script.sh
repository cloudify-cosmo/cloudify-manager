key_path=$1
cloudify_agents_kp=$2
host_name=$3
management_ip=$4
image_name=$5
security_group=$6
management_network_name=$7

pip install .

python sanity.py \
    --key_path=$key_path \
    --key_name=$key_name \
    --host_name=$host_name \
    --management_ip=$management_ip \
    --image_name=$image_name \
    --security_group=$security_group \
    --management_network_name=$management_network_name

# python sanity.py \
#     --key_path='~/.ssh/cloudify-agents-kp.pem' \
#     --key_name=cloudify-agents-kp \
#     --host_name=dank_hello_world_vm \
#     --management_ip=15.185.158.169 \
#     --image_name='Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)'
#     --security_group='cloudify-sg-agents' \
#     --management_network_name='cloudify-admin-network'