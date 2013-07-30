__author__ = 'elip'

from fabric.api import local as lrun
import timeout_decorator

from decorators import retry

USER_HOME = "/home/vagrant"
WORKING_DIR = USER_HOME + "/cosmo-work"
VERSION = "0.1-SNAPSHOT"
JAR_NAME = "orchestrator-" + VERSION + "-all"
JAVA_OPTS = "-Xms512m -Xmx1024m -XX:PermSize=128m"


def install_rabbitmq():

    with open("/etc/apt/sources.list", "a") as sources:
        sources.write("deb http://www.rabbitmq.com/debian/ testing main")

    run_with_retry_and_timeout("wget http://www.rabbitmq.com/rabbitmq-signing-key-public.asc")
    run_with_retry_and_timeout("apt-key add rabbitmq-signing-key-public.asc")
    run_with_retry_and_timeout("apt-get update")
    run_with_retry_and_timeout("apt-get install -q -y erlang-nox")
    run_with_retry_and_timeout("apt-get -y -f install")
    run_with_retry_and_timeout("apt-get install -q -y rabbitmq-server")
    lrun("rabbitmq-plugins enable rabbitmq_management")
    lrun("rabbitmq-plugins enable rabbitmq_tracing")
    lrun("service rabbitmq-server restart")
    lrun("rabbitmqctl trace_on")


def install_lxc_docker():
    run_with_retry_and_timeout("apt-get install -q -y python-software-properties")
    run_with_retry_and_timeout("apt-get update -qq")
    run_with_retry_and_timeout("add-apt-repository -y ppa:dotcloud/lxc-docker")
    run_with_retry_and_timeout("apt-get update -qq")
    run_with_retry_and_timeout("apt-get install -q -y lxc-docker")


def install_kernel():
    run_with_retry_and_timeout("add-apt-repository -y ppa:ubuntu-x-swat/r-lts-backport")
    run_with_retry_and_timeout("apt-get update -qq")
    run_with_retry_and_timeout("apt-get install -q -y linux-image-3.8.0-19-generic")


def install_riemann():
    run_with_retry_and_timeout("wget http://aphyr.com/riemann/riemann_0.2.2_all.deb")
    lrun("sudo dpkg -i riemann_0.2.2_all.deb")


def install_java():
    run_with_retry_and_timeout("sudo apt-get -y install openjdk-7-jdk")


def install_celery():
    run_with_retry_and_timeout("pip install billiard==2.7.3.28")
    run_with_retry_and_timeout("pip install --default-timeout=120 celery==3.0.19")
    run_with_retry_and_timeout("pip install python-vagrant")
    run_with_retry_and_timeout("pip install bernhard")


def install_vagrant():
    run_with_retry_and_timeout(
        "wget http://files.vagrantup.com/packages/22b76517d6ccd4ef232a4b4ecbaa276aff8037b8/vagrant_1.2.6_x86_64.deb"
    )
    lrun("sudo dpkg -i vagrant_1.2.6_x86_64.deb")


def install_vagrant_lxc():
    lrun("vagrant plugin install vagrant-lxc")


def install_guest_additions():
    run_with_retry_and_timeout("apt-get install -q -y linux-headers-3.8.0-19-generic dkms")
    lrun("echo 'Downloading VBox Guest Additions...'")
    run_with_retry_and_timeout(
        "wget -q http://dlc.sun.com.edgesuite.net/virtualbox/4.2.12/VBoxGuestAdditions_4.2.12.iso"
    )

    guest_additions_script = """mount -o loop,ro /home/vagrant/VBoxGuestAdditions_4.2.12.iso /mnt
echo yes | /mnt/VBoxLinuxAdditions.run
umount /mnt
rm /root/guest_additions.sh
"""

    lrun("echo -e '" + guest_additions_script + "' > /root/guest_additions.sh")
    lrun("chmod 700 /root/guest_additions.sh")
    lrun("sed -i -E 's#^exit 0#[ -x /root/guest_additions.sh ] \\&\\& /root/guest_additions.sh#' /etc/rc.local")
    lrun("echo 'Installation of VBox Guest Additions is proceeding in the background.'")
    lrun("echo '\"vagrant reload\" can be used in about 2 minutes to activate the new guest additions.'")


def install_git():
    run_with_retry_and_timeout("apt-get -y install git-core")


def install_maven():
    run_with_retry_and_timeout(
        "wget http://apache.mivzakim.net/maven/maven-3/3.1.0/binaries/apache-maven-3.1.0-bin.tar.gz"
    )
    lrun("tar -xzvf apache-maven-3.1.0-bin.tar.gz -C /opt")


def install_cosmo():

    run_script = """#!/bin/sh
ARGS=\"$@\"
java {0} -jar {1}/{2}.jar $ARGS
""".format(JAVA_OPTS, WORKING_DIR, JAR_NAME)

    get_cosmo = "wget https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/" \
                ".m2/repository/org/cloudifysource/cosmo/orchestrator/" + VERSION + "/" + JAR_NAME + ".jar"

    run_with_retry_and_timeout(get_cosmo)

    cosmo_exec = open("cosmo.sh", "w")
    cosmo_exec.write(run_script)

    lrun("sudo chmod +x " + WORKING_DIR + "/cosmo.sh")

    lrun("echo \"alias cosmo='{0}/cosmo.sh'\" > {1}/.bash_aliases".format(WORKING_DIR, USER_HOME))


def add_precise64_lxc_box():
    run_with_retry_and_timeout(
        "vagrant box add precise64 http://dl.dropbox.com/u/13510779/lxc-precise-amd64-2013-07-12.box"
    )


def reboot():
    lrun("shutdown -r +1")



@retry(tries=3, delay=2, backoff=2)
def run_with_retry_and_timeout(command):
    try:
        print command
        run_with_timeout(command)
        return True
    except timeout_decorator.TimeoutError:
        print "Execution of command {0} timed out".format(command)
        return False
    except SystemExit:
        print "Execution of command {0} failed".format(command)
        return False


@timeout_decorator.timeout(60 * 10)  # 10 minute default command timeout
def run_with_timeout(command):
    lrun(command)


def main():
    install_lxc_docker()
    install_kernel()
    install_rabbitmq()
    install_riemann()
    install_celery()
    install_java()
    install_maven()
    install_vagrant()
    install_vagrant_lxc()
    install_java()
    install_cosmo()
    print "Manager boot completed"

if __name__ == '__main__':
    main()