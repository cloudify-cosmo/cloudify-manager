import subprocess
import sys

__author__ = 'elip'

from subprocess import CalledProcessError
from retrying import retry
import timeout_decorator

USER_HOME = "/home/vagrant"
WORKING_DIR = USER_HOME + "/cosmo-work"
VERSION = "0.1-SNAPSHOT"
JAR_NAME = "orchestrator-" + VERSION + "-all"
JAVA_OPTS = "-Xms512m -Xmx1024m -XX:PermSize=128m"


@retry(stop='stop_after_attempt', stop_max_attempt_number=3, wait_fixed=3000)
def install_fabric():
    return_code = subprocess.call(["sudo", "pip", "install", "fabric"])
    if return_code != 0:
        raise CalledProcessError(cmd="pip install fabric", returncode=1, output=sys.stderr)


def install_rabbitmq():

    run_fabric(sudo("sed -i '2i deb http://www.rabbitmq.com/debian/ testing main' /etc/apt/sources.list"))

    wget("http://www.rabbitmq.com/rabbitmq-signing-key-public.asc")
    apt_key("rabbitmq-signing-key-public.asc")
    apt_get("update")
    apt_get("install -q -y erlang-nox")
    apt_get("install -y -f ")
    apt_get("install -q -y rabbitmq-server")
    run_fabric(sudo("rabbitmq-plugins enable rabbitmq_management"))
    run_fabric(sudo("rabbitmq-plugins enable rabbitmq_tracing"))
    run_fabric(sudo("service rabbitmq-server restart"))
    run_fabric(sudo("rabbitmqctl trace_on"))


def install_lxc_docker():
    apt_get("install -q -y python-software-properties")
    apt_get("update -qq")
    add_apt("-y ppa:dotcloud/lxc-docker")
    apt_get("update -qq")
    apt_get("install -q -y lxc-docker")


def install_kernel():
    add_apt("-y ppa:ubuntu-x-swat/r-lts-backport")
    apt_get("update -qq")
    apt_get("install -q -y linux-image-3.8.0-19-generic")


def install_riemann():
    wget("http://aphyr.com/riemann/riemann_0.2.2_all.deb")
    run_fabric(sudo("dpkg -i riemann_0.2.2_all.deb"))


def install_java():
    apt_get("install -y openjdk-7-jdk")


def install_celery():
    pip("billiard==2.7.3.28")
    pip("celery==3.0.19")
    pip("python-vagrant")
    pip("bernhard")


def install_vagrant():
    wget("http://files.vagrantup.com/packages/22b76517d6ccd4ef232a4b4ecbaa276aff8037b8/vagrant_1.2.6_x86_64.deb")
    run_fabric(sudo("dpkg -i vagrant_1.2.6_x86_64.deb"))
    install_vagrant_lxc()
    add_precise64_lxc_box()


def install_vagrant_lxc():
    run_fabric("vagrant plugin install vagrant-lxc")


def install_guest_additions():
    apt_get("install -q -y linux-headers-3.8.0-19-generic dkms")
    run_fabric("echo 'Downloading VBox Guest Additions...'")
    wget("-q http://dlc.sun.com.edgesuite.net/virtualbox/4.2.12/VBoxGuestAdditions_4.2.12.iso")

    guest_additions_script = """mount -o loop,ro /home/vagrant/VBoxGuestAdditions_4.2.12.iso /mnt
echo yes | /mnt/VBoxLinuxAdditions.run
umount /mnt
rm /root/guest_additions.sh
"""

    run_fabric("echo -e '" + guest_additions_script + "' > /root/guest_additions.sh")
    run_fabric("chmod 700 /root/guest_additions.sh")
    run_fabric("sed -i -E 's#^exit 0#[ -x /root/guest_additions.sh ] \\&\\& /root/guest_additions.sh#' /etc/rc.local")
    run_fabric("echo 'Installation of VBox Guest Additions is proceeding in the background.'")
    run_fabric("echo '\"vagrant reload\" can be used in about 2 minutes to activate the new guest additions.'")


def install_cosmo():

    run_script = """#!/bin/sh
ARGS=\"$@\"
export VAGRANT_DEFAULT_PROVIDER=lxc
java {0} -jar {1}/{2}.jar $ARGS
""".format(JAVA_OPTS, WORKING_DIR, JAR_NAME)

    get_cosmo = "https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/" \
                ".m2/repository/org/cloudifysource/cosmo/orchestrator/" + VERSION + "/" + JAR_NAME + ".jar"

    wget(get_cosmo)

    script_path = WORKING_DIR + "/cosmo.sh"
    cosmo_exec = open(script_path, "w")
    cosmo_exec.write(run_script)

    run_fabric("chmod +x " + script_path)

    run_fabric("echo \"alias cosmo='{0}/cosmo.sh'\" > {1}/.bash_aliases".format(WORKING_DIR, USER_HOME))


def add_precise64_lxc_box():
    run_with_retry_and_timeout(
        "vagrant box add precise64 http://dl.dropbox.com/u/13510779/lxc-precise-amd64-2013-07-12.box"
    )


def reboot():
    run_fabric("shutdown -r +1")


def pip(package):
    run_with_retry_and_timeout(sudo("pip install --timeout=120 {0}".format(package)))


def sudo(command):
    return "sudo {0}".format(command)


def apt_get(command):
    run_with_retry_and_timeout(sudo("apt-get {0}".format(command)))


def add_apt(command):
    run_with_retry_and_timeout(sudo("add-apt-repository {0}".format(command)))


def apt_key(command):
    run_with_retry_and_timeout(sudo("apt-key add {0}".format(command)))


def wget(url):
    run_with_retry_and_timeout("wget {0} -P {1}/".format(url, WORKING_DIR))



@retry(stop='stop_after_attempt', stop_max_attempt_number=3, wait_fixed=3000)
def run_with_retry_and_timeout(command):
    try:
        print command
        run_with_timeout(command)
    except SystemExit:  # lrun does not throw exception, but just exists the process
        raise CalledProcessError(cmd=command, returncode=1, output=sys.stderr)


@timeout_decorator.timeout(60 * 10)  # 10 minute default command timeout
def run_with_timeout(command):
    run_fabric(command)


def run_fabric(command):
    from fabric.api import local as lrun
    lrun(command)


def main():
    install_fabric()
    install_lxc_docker()
    install_kernel()
    install_rabbitmq()
    install_riemann()
    install_celery()
    install_vagrant()
    install_java()
    install_cosmo()
    print "Manager boot completed"

if __name__ == '__main__':
    main()