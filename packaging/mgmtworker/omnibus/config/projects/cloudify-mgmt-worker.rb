#
# Copyright 2015 YOUR NAME
#
# All Rights Reserved.
#

name "cloudify-mgmt-worker"
maintainer "Gigaspaces"
homepage "http://getcloudify.org/"

override :cacerts, version: '2015.10.28', source: { md5: '782dcde8f5d53b1b9e888fdf113c42b9' }
override :pip, version: '8.1.1', source: { md5: '6b86f11841e89c8241d689956ba99ed7' }
override :setuptools, version: '18.5', source: { md5: '533c868f01169a3085177dffe5e768bb' }

install_dir "/opt/mgmtworker"

build_version Omnibus::BuildVersion.semver

ENV['BUILD'] || raise('BUILD environment variable not set')
build_iteration ENV['BUILD']

# Creates required build directories
dependency "preparation"

# rest-service dependencies/components
dependency "python"
dependency "pip"
dependency "mgmt-worker"

# Version manifest file
dependency "version-manifest"

exclude "**/.git"
exclude "**/bundler/git"
