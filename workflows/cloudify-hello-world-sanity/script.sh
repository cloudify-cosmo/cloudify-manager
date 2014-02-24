# key_path=$1
# cloudify_agents_kp=$2
# host_name=$3
# management_ip=$4
# region=$5
# image=$6

# pip install .

# python sanity.py \
#     --key_path=$key_path \
#     --key_name=$key_name \
#     --host_name=$host_name \
#     --management_ip=$management_ip \
#     --region=$region \
#     --image=$image

python sanity.py \
    --key_path='~/.ssh/cloudify-agents-kp.pem' \
    --key_name=cloudify-agents-kp \
    --host_name=dank_hello_world_vm \
    --management_ip=15.185.158.169 \
    --region='az-2.region-a.geo-1' \
    --image=67074
