FROM centos:7

RUN yum install -y deltarpm
RUN yum install -y epel-release
RUN yum install -y initscripts sudo openssh openssh-clients openssh-server \
	systemd-sysv openssl-1.0.2k libselinux-utils logrotate java python-setuptools \
	python-backports python-backports-ssl_match_hostname which
RUN ssh-keygen -A

ENV container=docker

# This is necessary for systemd to work properly. See the "Dockerfile for
#systemd base image" here: https://hub.docker.com/_/centos/
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

EXPOSE 22 80 443 5671 5672 15672 9200 5432 8086 999

# Should help to stop the container gracfully
STOPSIGNAL SIGRTMIN+3

RUN systemctl set-default multi-user.target
VOLUME [ "/sys/fs/cgroup" ]

# Workaround for docker/docker#27202, technique based on comments from docker/docker#9212
CMD ["/bin/bash", "-c", "exec /sbin/init --log-target=journal 3>&1"]
