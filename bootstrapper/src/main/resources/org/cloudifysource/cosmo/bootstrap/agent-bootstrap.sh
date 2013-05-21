#! /bin/bash

#############################################################################
# Parameters that should be exported beforehand:
# 	$COSMO_WORK_DIRECTORY - This directory holds the files that we're copied and will will server as
#                           root for most of the script actions.
#	$COSMO_URL - If this url is found, it will be downloaded to $COSMO_WORK_DIRECTORY/agent-all.jar
#   $COSMO_ENV_JAVA_URL - If this url is found it will be used to download the Java7 jdk.
#                         Otherwise, the default cloudify repository will be used.
#############################################################################

# args:
# $1 the error code of the last command (should be explicitly passed)
# $2 the message to print in case of an error
#
# an error message is printed and the script exists with the provided error code
function error_exit {
	echo "$2 : error code: $1"
	exit ${1}
}

# args:
# $1 the error code of the last command (should be explicitly passed)
# $2 the message to print in case of an error
# $3 the threshold to exit on
#
# if (last_error_code [$1]) >= (threshold [$3]) the provided message[$2] is printed and the script
# exists with the provided error code ($1)
function error_exit_on_level {
	if [ ${1} -ge ${3} ]; then
		error_exit ${1} ${2}
	fi
}

# Load supplied enviroment variables.
ENV_FILE_PATH=${COSMO_WORK_DIRECTORY}bootstrap-env.sh
if [ -f ${ENV_FILE_PATH} ]; then
	source ${ENV_FILE_PATH}
fi

JAVA_32_URL="http://repository.cloudifysource.org/com/oracle/java/1.7.0_21/jdk-7u21-linux-i586.tar.gz"
JAVA_64_URL="http://repository.cloudifysource.org/com/oracle/java/1.7.0_21/jdk-7u21-linux-x64.tar.gz"

# If not JDK specified, determine which JDK to install based on hardware architecture
if [ -z "$COSMO_ENV_JAVA_URL" ]; then
	ARCH=`uname -m`
	echo Machine Architecture -- $ARCH
	if [ "$ARCH" = "i686" ]; then
		export COSMO_ENV_JAVA_URL=$JAVA_32_URL
	elif [ "$ARCH" = "x86_64" ]; then
		export COSMO_ENV_JAVA_URL=$JAVA_64_URL
	else
		echo Unknown architecture -- $ARCH -- defaulting to 32 bit JDK
		export COSMO_ENV_JAVA_URL=$JAVA_32_URL
	fi
fi

if [ "$COSMO_ENV_JAVA_URL" = "NO_INSTALL" ]; then
	echo "JDK will not be installed"
else
	echo Previous JAVA_HOME value -- $JAVA_HOME
	export COSMO_ORIGINAL_JAVA_HOME=$JAVA_HOME

	echo Downloading JDK from $COSMO_ENV_JAVA_URL
	wget -q -O $COSMO_WORK_DIRECTORY/java.tar.gz $COSMO_ENV_JAVA_URL || error_exit $? "Failed downloading Java installation from $COSMO_ENV_JAVA_URL"
	rm -rf ~/java || error_exit $? "Failed removing old java installation directory"
	mkdir ~/java
	cd ~/java

	echo Extracting JDK
    tar xfz $COSMO_WORK_DIRECTORY/java.tar.gz -C ~/java || error_exit_on_level $? "Failed extracting cloudify installation" 2
	mv ~/java/*/* ~/java || error_exit $? "Failed moving JDK installation"
    export JAVA_HOME=~/java

    cd $COSMO_WORK_DIRECTORY
fi

if [ ! -z "$COSMO_URL" ]; then
	echo Downloading Cosmo agent from $COSMO_URL
	wget -q $COSMO_URL -O $COSMO_WORK_DIRECTORY/agent-all.jar || error_exit $? "Failed downloading cosmo agent installation"
fi

COMMAND="$JAVA_HOME/jre/bin/java -cp $COSMO_WORK_DIRECTORY/agent-all.jar -Dcosmo.agent.properties-location=$COSMO_WORK_DIRECTORY/bootstrap.properties org.cloudifysource.cosmo.agent.AgentProcess"
echo $COMMAND
nohup $COMMAND | tee /dev/null

