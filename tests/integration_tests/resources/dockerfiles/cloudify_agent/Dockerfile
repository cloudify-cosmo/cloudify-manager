FROM amd64/centos:7
MAINTAINER Cosmo (hello@cloudify.co)
ENV container docker
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;
VOLUME [ "/sys/fs/cgroup" ]
RUN yum -y update && yum clean all
RUN yum -y install python-devel gcc openssl git libxslt-devel libxml2-devel openldap-devel libffi-devel openssl-devel libvirt-devel sudo which python-backports-ssl_match_hostname systemd-sysv logrotate python-setuptools python-backports openssh-server cronie epel-release libselinux-utils libselinux libselinux-python selinux-policy selinux-policy
RUN curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
RUN python get-pip.py
RUN pip install --upgrade pip==9.0.1
RUN pip install https://github.com/cloudify-cosmo/cloudify-common/archive/master.zip
WORKDIR /root
COPY script.py /root/script.py
RUN chmod 775 /root/script.py
RUN echo "NETWORKING=yes" > /etc/sysconfig/network
CMD ["/usr/sbin/init"]
