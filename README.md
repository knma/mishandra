# mishandra

## Overview
Simple distributed data storage and usage.

## Cassandra setup

### Windows
1. Download the latest stable [Cassandra](https://cassandra.apache.org/download/), unpack and put it into a persistent directory.
2. Set **CASSANDRA_HOME** environment variable.
3. Add **CASSANDRA_HOME**\bin to **PATH** environment variable (e.g. ```C:\Program Files\apache-cassandra-3.11.6\bin```).
4. Download [Amazon Corretto](https://docs.aws.amazon.com/en_us/corretto/latest/corretto-8-ug/downloads-list.html) (JDK for Windows 64) and install it with default settings.

To start Cassandra, open PowerShell as administrator and run ```cassandra -f```. If you get ```WARNING! Powershell script execution unavailable```, please run ```Set-ExecutionPolicy Unrestricted```.
