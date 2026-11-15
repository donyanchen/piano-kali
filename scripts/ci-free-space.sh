#!/bin/bash
# Strip toolchains the Kali build does not need. The root filesystem image plus
# the qemu-user package install need roughly 30 GiB in /.
set -euxo pipefail
df -h /
sudo rm -rf /usr/share/dotnet
sudo rm -rf /usr/local/lib/android
sudo rm -rf /opt/ghc
sudo rm -rf /opt/hostedtoolcache/CodeQL
sudo rm -rf /usr/local/share/boost
sudo rm -rf /usr/share/swift
sudo rm -rf /usr/local/graalvm
sudo rm -rf /usr/local/.ghcup
sudo rm -rf /usr/share/sbt
sudo rm -rf /usr/lib/jvm
sudo apt-get clean
df -h /
