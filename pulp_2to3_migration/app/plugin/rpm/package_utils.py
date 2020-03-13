import logging

from gettext import gettext as _


_LOGGER = logging.getLogger(__name__)


def nevra(name):
    """
    Parse NEVRA.
    Inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA
    We don't use hawkey because it is not available on all platforms we support.

    Args:
        name(string): NEVRA (jay-3:3.10-4.fc3.x86_64)

    Returns:
        tuple: parsed NEVRA (name, epoch, version, release, architecture)

    """
    if name.count(".") < 1:
        msg = _("failed to parse nevra '%s' not a valid nevra") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    arch_dot_pos = name.rfind(".")
    arch = name[arch_dot_pos + 1:]

    return nevr(name[:arch_dot_pos]) + (arch, )


def nevr(name):
    """
    Parse NEVR.
    Inspired by:
    https://github.com/rpm-software-management/hawkey/blob/d61bf52871fcc8e41c92921c8cd92abaa4dfaed5/src/util.c#L157. # NOQA

    Args:
        name(string): NEVR "jay-test-3:3.10-4.fc3"

    Returns:
       tuple: parsed NEVR (name, epoch, version, release)

    """
    if name.count("-") < 2:  # release or name is missing
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    release_dash_pos = name.rfind("-")
    release = name[release_dash_pos + 1:]
    name_epoch_version = name[:release_dash_pos]
    name_dash_pos = name_epoch_version.rfind("-")
    package_name = name_epoch_version[:name_dash_pos]

    epoch_version = name_epoch_version[name_dash_pos + 1:].split(":")
    if len(epoch_version) == 1:
        epoch = 0
        version = epoch_version[0]
    elif len(epoch_version) == 2:
        epoch = int(epoch_version[0])
        version = epoch_version[1]
    else:
        # more than one ':'
        msg = _("failed to parse nevr '%s' not a valid nevr") % name
        _LOGGER.exception(msg)
        raise ValueError(msg)

    return package_name, epoch, version, release
