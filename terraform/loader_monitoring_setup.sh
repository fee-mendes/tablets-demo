#!/bin/bash

SEED_IP="172.31.0.101"
APP_IP="172.31.0.201"
INSTANCE_IP="$(ip a show | sed -En -e 's/.*inet (172.31.[0-9.]+).*/\1/p')"


# We use ScyllaDB 5.4 cassandra-stress to cirvumvent https://github.com/scylladb/scylla-enterprise/issues/4669
# Maybe there's a release with enterprise fixed, but I didn't bothered checking.

gpg --homedir /tmp --no-default-keyring --keyring /etc/apt/keyrings/scylladb.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys D0A112E067426AB2
wget -O /etc/apt/sources.list.d/scylla.list https://s3.amazonaws.com/downloads.scylladb.com/deb/ubuntu/scylla-5.4.list

apt-get update
apt-get install -y docker.io scylla-cqlsh scylla-tools scylla-tools-core openjdk-11-jre-headless git python3 python3-pip
usermod -aG docker ubuntu

# Now that we ensured we have a decent cassandra-stress, we need to retrieve the latest Java driver for Tablet routing.
# Someone please fix this mess.

docker pull scylladb/cassandra-stress:latest
docker run -dit --name cs scylladb/cassandra-stress:latest bash

# Finally COPY 
rm /opt/scylladb/share/cassandra/lib/scylla-driver-core-3.11.5.1-shaded.jar
docker cp cs:/scylla-tools-java/lib/scylla-driver-core-3.11.5.3-shaded.jar /opt/scylladb/share/cassandra/lib/
chmod 644 /opt/scylladb/share/cassandra/lib/scylla-driver-core-3.11.5.3-shaded.jar
chown root.root /opt/scylladb/share/cassandra/lib/scylla-driver-core-3.11.5.3-shaded.jar

# And cleanup
docker rm -f cs
docker volume prune --force

mkdir -pv /loader /app

# cqlsh credentials
mkdir -pv /home/ubuntu/.cassandra/
cat > /home/ubuntu/.cassandra/credentials << "EOF"
[PlainTextAuthProvider]
username = cassandra
password = cassandra
EOF

chown -R ubuntu:ubuntu /home/ubuntu/.cassandra
chmod 600 /home/ubuntu/.cassandra/credentials

# Monitoring and App Setup
if [ "${INSTANCE_IP}" == "${APP_IP}" ]; then

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

wget https://github.com/scylladb/scylla-monitoring/archive/refs/tags/4.8.1.tar.gz -O /loader/monitoring.tar.gz
cd /loader

tar -zxf monitoring.tar.gz

cd /loader/scylla-monitoring-4.8.1
cat > prometheus/scylla_servers.yml << EOF

- targets:
       - 172.31.0.101
       - 172.31.0.102
       - 172.31.0.103
       - 172.31.0.104
       - 172.31.0.105
       - 172.31.0.106
  labels:
       cluster: cluster
       dc: dc

EOF

# We only need Prom and Grafana really...
/loader/scylla-monitoring-4.8.1/start-all.sh -v 2024.2 -s prometheus/scylla_servers.yml --no-loki --no-renderer --no-alertmanager --no-cas --no-cdc -c GF_SECURITY_ALLOW_EMBEDDING=true

# App stuff
cd /app
git clone https://github.com/ruthea/tablets-demo.git
cd /app/tablets-demo

# Configure Ansible inventory
cat > /app/tablets-demo/ansible/inventory.ini << EOF
[base]
172.31.0.101
172.31.0.102
172.31.0.103

[scale]
172.31.0.104
172.31.0.105
172.31.0.106

[monitoring]
172.31.0.201

[loader]
172.31.0.201
172.31.0.202
172.31.0.203
EOF

chown -R ubuntu:ubuntu /app
su - ubuntu -c 'pip3 install -r /app/tablets-demo/requirements.txt'
su - ubuntu -c 'pip3 install wait-for-it'

# Set-up systemd service unit. TODO: Init CQL/data load only once.
cat > /etc/systemd/system/webapp.service << EOF
[Unit]
Description=Tablets Demo
After=syslog.target network.target remote-fs.target nss-lookup.target

[Service]
Environment=PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin
Type=simple
User=ubuntu
WorkingDirectory=/app/tablets-demo
ExecStart=/home/ubuntu/.local/bin/wait-for-it --service 172.31.0.103:9042 --service 172.31.0.102:9042 --service 172.31.0.101:9042 -t 0 -- /usr/bin/python3 app.py --seed-node ${SEED_IP} --monitoring-ip ${PUBLIC_IP} -i
Restart=never
LimitNOFILE=50000

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Note, there's a race condition here:
# If the Terraform provisioner hasn't yet copied the private key to this (201) node, the initial ingestion will fail.
# This shouldn't be the case most of the time as the setup takes some considerable time already. BUT, be aware of it.
# And sleep just in case :-)

sleep 120
systemctl start webapp

fi
