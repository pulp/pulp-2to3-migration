from django.db import models


class Pulp2GlobalImporterConfig(models.Model):
    """
    proxy_url:
        A string in the form of scheme://host, where scheme is either http or https
    proxy_port:
        An integer representing the port number to use when connecting to the proxy server
    proxy_username:
        If provided, Pulp will attempt to use basic auth with the proxy server using this
        as the username
    proxy_password:
        If provided, Pulp will attempt to use basic auth with the proxy server using this
        as the password
    connect_timeout:
        Number of seconds to wait for nectar to establish a connection with a remote machine.
        It’s a good practice to set connect timeouts to slightly larger than a multiple of 3,
        which is the default TCP packet retransmission window. Default is 6.05.
    read_timeout:
        The number of seconds the client will wait for the server to send a response after an
        initial connection has already been made. Defaults to 27.
    """

    plugin = models.CharField(max_length=255)
    proxy_url = models.TextField(null=True)
    proxy_port = models.IntegerField(null=True)
    proxy_username = models.TextField(null=True)
    proxy_password = models.TextField(null=True)
    connect_timeout = models.FloatField(null=True)
    read_timeout = models.IntegerField(null=True)
