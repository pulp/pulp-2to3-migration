# pulp-2to3-migrate

A [Pulp 3](https://pulpproject.org/) plugin to migrate from Pulp 2 to Pulp 3.

### Requirements

* /var/lib/pulp is shared from Pulp 2 machine
* access to Pulp 2 database

### Configuration
On Pulp 2 machine:

1. Make sure MongoDB listens on the IP address accesible outside, it should be configured as 
one of the `bindIP`s in /etc/mongod.conf.

2. In case /var/lib/pulp is not on a shared filesystem, configure NFS server and share 
that directory. E.g. on Fedora/CentOS:

```
$ sudo dnf install nfs-utils
$ sudo systemctl start nfs-server
$ sudo vi /etc/exports:

        /var/lib/pulp          <Pulp 3 IP address>(rw,sync,no_root_squash,no_subtree_check)
        
$ sudo exportfs -a
```

On Pulp 3 machine:
1. Mount /var/lib/pulp to your Pulp 3 storage location. By default, it's /var/lib/pulp. E.g. on 
Fedora/Centos:

```
$ sudo dnf install nfs-utils
$ sudo mount <IP address of machine which exports /var/lib/pulp>:/var/lib/pulp /var/lib/pulp
```

### Installation

Clone repositories for the base tool and extensions for the plugins of interest, and install them.
```
$ git clone https://github.com/pulp/pulp-2to3-migrate.git
$ pip install -e pulp-2to3-migrate
$
$ git clone https://github.com/pulp/pulp-2to3-migrate-iso.git
$ pip install -e pulp-2to3-migrate-iso
```