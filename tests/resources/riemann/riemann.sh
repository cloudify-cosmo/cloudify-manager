#!/bin/bash -e

CONFIG=$1

RIEMANN_HOME="$(dirname $(which riemann))/../"

# Path in manual installation
RIEMANN_JAR="${RIEMANN_HOME}/lib/riemann.jar"
if [[ ! -f "${RIEMANN_JAR}" ]]; then
    # Path when installing .deb package
    RIEMANN_JAR="/usr/lib/riemann/riemann.jar"
    if [[ ! -f "${RIEMANN_JAR}" ]]; then
    # # Path when installing with brew
    RIEMANN_JAR="/usr/local/Cellar/riemann/0.2.6/libexec/lib/riemann.jar"
        if [[ ! -f "${RIEMANN_JAR}" ]]; then
            echo "Failed locating riemann.jar"
            exit 1
        fi
    fi
fi

# Injected by test, otherwise, checks if it sits next to riemann.jar
LANGOHR_JAR="${LANGOHR_JAR=${RIEMANN_HOME}/lib/langohr.jar}"

if [[ ! -f "${LANGOHR_JAR}" ]]; then
    echo "Failed locating langohr.jar"
    exit 1
fi

MAIN_CLASS="riemann.bin"
OPTS="-XX:+UseConcMarkSweepGC \
      -XX:+UseParNewGC \
      -XX:+CMSParallelRemarkEnabled \
      -XX:+AggressiveOpts \
      -XX:+UseFastAccessorMethods \
      -XX:+UseCompressedOops \
      -XX:+CMSClassUnloadingEnabled"

exec java ${OPTS} -cp "${LANGOHR_JAR}:${RIEMANN_JAR}" ${MAIN_CLASS} ${CONFIG}
