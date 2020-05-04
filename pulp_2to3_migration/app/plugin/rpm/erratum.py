import datetime
import logging

import createrepo_c as cr

from django.utils.dateparse import parse_datetime


_logger = logging.getLogger(__name__)


def get_pulp2_filtered_collections(pulp2erratum, repo_pkg_nevra, repo_module_nsvca):
    """
    Make a lists of package collections which will be in the migrated advisory.

    Only packages contained in a repository being migrated will be included in this pkglist.

    This merges multiple Pulp collections into a single one, unless it's a modular erratum, then a
    a separate collection is used for each module.

    Args:
        pulp2erratum: a pre-migrated erratum to be migrated
        repo_pkg_nevra: list of NEVRA tuples for the packages in a repository this erratum is
                        being migrated for
        repo_module_nsvca: list of NSVCA tuples for the modules in a repository this erratum is
                           being migrated for

    Return:
        A pkglist to migrate

    """
    def get_module_nsvca(module):
        return (module['name'],
                module['stream'],
                int(module['version']),
                module['context'],
                module['arch'])

    def get_pkg_nevra(pkg):
        return (pkg['name'],
                pkg['epoch'] or '0',
                pkg['version'],
                pkg['release'],
                pkg['arch'])

    filtered_pkglist = []
    default_collection = {'name': 'default',
                          'short': 'def',
                          'packages': []}
    filtered_pkglist.append(default_collection)
    if not repo_pkg_nevra:
        # If there are no packages in a repo, no pkglist will ever contain packages.
        # Return a pkglist with one empty collection (an empty pkglist is not allowed).
        return filtered_pkglist

    seen_non_modular_packages = set()
    seen_modules = set()
    for collection in pulp2erratum.pkglist:
        module = collection.get('module')
        if module:
            # inside a modular collection
            nsvca = get_module_nsvca(module)
            if nsvca in seen_modules or nsvca not in repo_module_nsvca:
                # already processed or not from the repo being migrated
                continue
            seen_modules.add(nsvca)
            current_collection = {'name': collection.get('name'),
                                  'short': collection.get('short'),
                                  'module': module,
                                  'packages': []}
            filtered_pkglist.append(current_collection)
        else:
            # the first and default collection collects the non-modular packages
            current_collection = filtered_pkglist[0]
            current_collection['name'] = collection.get('name')
            current_collection['short'] = collection.get('short')

        for package in collection.get('packages', []):
            if not module:
                # only non-modular packages are tracked;
                # modular packages are not tracked because the same package can be present
                # in different modules and duplicated modules are already filtered out.
                if package['filename'] in seen_non_modular_packages:
                    continue
                seen_non_modular_packages.add(package['filename'])
            nevra = get_pkg_nevra(package)
            if nevra in repo_pkg_nevra:
                current_collection['packages'].append(package)

    return filtered_pkglist


def get_package_checksum(errata_pkg):
    """
    Extract package checksum and checksum type from a pulp 2 package listed in an erratum.

    Handle two possible ways of specifying the checksum in the erratum package list:
        - in the `sum` package field as a list of alternating checksum types and values,
          e.g. ['type1', 'checksum1', 'type2', 'checksum2']. Createrepo_c supports only ine
          checksum per package.
        - in the `type` and `sums` package fields. It is only the case when the erratum was uploaded
          via pulp-admin. Only one type of the checksum could be specified this way.

    Args:
        errata_pkg(dict): a package from an erratum to get a checksum for

    Returns:
        If found, a tuple with a checksum type id in createrepo_c and a checksum itself

    """
    checksums = errata_pkg.get('sum', [])
    checksum_type_v2 = errata_pkg.get('type')
    checksum_v2 = errata_pkg.get('sums')
    if checksum_type_v2 and checksum_v2:
        checksums.extend([checksum_type_v2, checksum_v2])

    if not checksums:
        return

    checksum_type_id = None
    checksum = None
    # createrepo_c supports one checksum per package, so the first suitable is picked
    for i in range(0, len(checksums), 2):
        try:
            checksum_type_id = getattr(cr, checksums[i].upper())
        except AttributeError:
            continue
        else:
            checksum = checksums[i + 1]
            break

    if checksum_type_id:
        return (checksum_type_id, checksum)


def get_bool(value):
    """
    Convert a value from an erratum to a boolean.

    Sometimes the value is None, some times it's an int, and sometimes it's a string with a boolean
    value, e.g. "True".

    Args:
        value: value of some errata field which has boolean semantics

    Returns:
        bool: interpreted value

    """
    if value:
        if isinstance(value, str) and value.lower() == 'true':
            return True
        if isinstance(value, int):
            return bool(value)
    return False


def get_datetime(datetime_str):
    """
    Convert a pulp2 datetime value to the Django one.

    Supported pulp 2 formats are:

        * '%Y-%m-%d %H:%M:%S UTC'
        * '%Y-%m-%d %H:%M:%S'
        * '%Y-%m-%d %H:%M'
        * '%Y-%m-%d'

    Django's `parse_datetime` can't deal with the first and last formats described above.

    Args:
        datetime_str: value of errata field which contains datetime

    Returns:
        datetime.datetime: datetime in the Django-acceptable format

    """
    # remove UTC part
    if datetime_str.endswith(' UTC'):
        datetime_str = datetime_str[:-4]

    # if it's as short as '%Y-%m-%d', try adding time so `parse_datetime` could parse it
    if len(datetime_str.strip()) == 10:
        datetime_str = f'{datetime_str.strip()} 00:00'

    datetime_obj = parse_datetime(datetime_str)
    if not datetime_obj:
        _logger.warn(f'Unsupported datetime format {datetime_str}, resetting to 1970-01-01 00:00')
        datetime_obj = datetime.datetime(1970, 1, 1, 0, 0)

    return datetime_obj
