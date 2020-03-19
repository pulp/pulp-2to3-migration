"""
Convert data from mongo to libcomps

"""

import libcomps

from pulp_rpm.app.comps import dict_to_strdict, list_to_idlist


def langpacks_to_libcomps(obj):
    """
    Convert standard dict to langpacks libcomps StrDict type object.

    Args:
        obj(Pulp2PackageLangpacks): Pulp2PackageLangpacks

    Returns:
        strdict: a libcomps StrDict

    """
    strdict = libcomps.StrDict()
    for dct in obj.matches:
        strdict[dct['name']] = dct['install']
    return strdict


def pkg_cat_to_libcomps(obj):
    """
    Convert PackageCategory object to libcomps Category object.

    Args:
        obj(Pulp2PackageCategory): Pulp2PackageCategory

    Returns:
        group: libcomps.Category object

    """
    cat = libcomps.Category()

    cat.id = obj.package_category_id
    cat.name = obj.name
    cat.desc = obj.description
    cat.display_order = obj.display_order
    cat.group_ids = list_to_idlist(_packages_to_grplist(obj.packagegroupids))
    cat.desc_by_lang = dict_to_strdict(obj.desc_by_lang)
    cat.name_by_lang = dict_to_strdict(obj.name_by_lang)

    return cat


def pkg_grp_to_libcomps(obj):
    """
    Convert PackageGroup object to libcomps Group object.

    Args:
        obj(Pulp2PackageGroup): Pulp2PackageGroup

    Returns:
        group: libcomps.Group object

    """
    group = libcomps.Group()

    group.id = obj.package_group_id
    group.default = obj.default
    group.uservisible = obj.user_visible
    group.display_order = obj.display_order
    group.name = obj.name
    group.desc = obj.description
    group.packages = _list_to_pkglist(obj.packages)
    group.biarchonly = obj.biarch_only
    group.desc_by_lang = dict_to_strdict(obj.desc_by_lang)
    group.name_by_lang = dict_to_strdict(obj.name_by_lang)

    return group


def pkg_env_to_libcomps(obj):
    """
    Convert PackageEnvironment object to libcomps Environment object.

    Args:
        obj(Pulp2PackageEnvironment): Pulp2PackageEnvironment

    Returns:
        group: libcomps.Environment object

    """
    env = libcomps.Environment()

    env.id = obj.package_environment_id
    env.name = obj.name
    env.desc = obj.description
    env.display_order = obj.display_order
    env.group_ids = list_to_idlist(_packages_to_grplist(obj.group_ids))
    result = _packages_to_optionlist(obj.option_ids)
    env.option_ids = list_to_idlist(result)
    env.desc_by_lang = dict_to_strdict(obj.desc_by_lang)
    env.name_by_lang = dict_to_strdict(obj.name_by_lang)

    return env


def _packages_to_grplist(packages):
    """
    Populate group_list with packages info

    Args:
        packages: list of packages

    Returns:
        A list

    """
    return [{'name': pkg, 'default': False} for pkg in packages]


def _list_to_pkglist(packages):
    """
    Convert list of Packages to libcomps PackageList object.

    Args:
        list: a list of Packages

    Returns:
        pkglist: a libcomps PackageList

    """
    pkglist = libcomps.PackageList()

    for pkg_lst in packages:
        for pkg in pkg_lst[1]:
            lib_pkg = libcomps.Package()
            if isinstance(pkg, list):
                lib_pkg.name = pkg[0]
                lib_pkg.requires = pkg[1]
            else:
                lib_pkg.name = pkg
            lib_pkg.type = pkg_lst[0]
            pkglist.append(lib_pkg)

    return pkglist


def _packages_to_optionlist(packages):
    """
    Populate option_list with package info.

    Args:
        packages: list of packages

    Returns:
        A list

    """
    option_list = []
    for pkg in packages:
        if not isinstance(pkg['default'], bool):
            if pkg['default'].lower() == 'false':
                pkg['default'] = False
            elif pkg['default'].lower() == 'true':
                pkg['default'] = True
        option_list.append({'name': pkg['group'],
                            'default': pkg['default']})
    return option_list
