"""
To render xml snippets for RPM.

Mostly ported from Pulp 2.

"""

import gzip
import re
from collections import namedtuple

import createrepo_c as cr
from django.template import (
    Context,
    Template,
)
from django.template.defaulttags import TemplateTagNode


ESCAPE_TEMPLATE_VARS_TAGS = {
    'primary': ('description', 'summary'),
    'other': ('changelog',)}
METADATA_TYPES = ('primary', 'other', 'filelists')

XmlElement = namedtuple('xml_element', ['start', 'end'])


def _substitute_special_chars(template):
    """
    Make the substitution of the syntax characters with the corresponding templatetag.
    The syntax characters to be substituted can be found in
    django.template.defaulttags.TemplateTagNode.mapping.

    Args:
        template(str): a piece of the template in which substitution should happen

    Returns:
        str: string with syntax characters substituted

    """
    templatetag_map = dict((sym, name) for name, sym in TemplateTagNode.mapping.items())
    symbols_pattern = '(%s)' % '|'.join(templatetag_map.keys())
    return re.sub(
        symbols_pattern,
        lambda mobj: '{%% templatetag %s %%}' % templatetag_map[mobj.group(1)],
        template
    )


def _generate_tag_replacement_str(mobj):
    """
    Generate replacement string for the matched XML element.

    Args:
        mobj(_sre.SRE_Match): matched object consisted of 3 groups:
                              opening tag, value and closing tag.

    Returns:
        str: replacement string for the given match object

    """
    start_tag = mobj.group(1)
    value = _substitute_special_chars(mobj.group(2))
    end_tag = mobj.group(3)
    return start_tag + value + end_tag


def _escape_django_syntax_chars(template, tag_name):
    """
    Escape Django syntax characters by replacing them with the corresponding templatetag.

    NOTE: This function does not handle the following XML syntax:
     - namespaces in the format of namespace_alias:tag_name
     - nested tag with the same name, e.g. <a><a>...</a></a>
    It is unlikely that the syntax above is used in the metadata of the content units.

    Args:
        template(str): a Django template
        tag_name(str): name of the element to wrap

    Returns:
        str: a Django template with the escaped syntax characters in the specified element

    """
    start_tag_pattern = r'<%s.*?(?<!/)>' % tag_name
    end_tag_pattern = r'</%s>' % tag_name
    complete_tag_pattern = r'(%s)(.*)(%s)' % (start_tag_pattern, end_tag_pattern)
    tag_re = re.compile(complete_tag_pattern, flags=re.DOTALL)
    template = tag_re.sub(_generate_tag_replacement_str, template)
    return template


def render_primary(template, checksum, checksumtype):
    """
    Render the primary XML with the requested checksum type and checksum.

    Args:
        template(str): a primary xml snippet template
        checksum(str): a checksum of a package to add to the template
        checksumtype(str): a checksum type to add to the template

    Returns:
        str: a rendered primary.xml snippet

    """
    for tag in ESCAPE_TEMPLATE_VARS_TAGS['primary']:
        template = _escape_django_syntax_chars(template, tag)
    context = Context({'checksum': checksum, 'checksumtype': checksumtype})
    return Template(template).render(context)


def render_other(template, checksum):
    """
    Render the other XML with the requested checksum type

    Args:
        template(str): a primary xml snippet template
        checksum(str): a checksum of a package to add to the template

    Returns:
        str: a rendered other.xml snippet

    """

    for tag in ESCAPE_TEMPLATE_VARS_TAGS['other']:
        template = _escape_django_syntax_chars(template, tag)
    context = Context({'pkgid': checksum})
    return Template(template).render(context)


def render_filelists(template, checksum):
    """
    Render the filelists XML with the requested checksum type

    Args:
        template(str): a primary xml snippet template
        checksum(str): a checksum of a package to add to the template

    Returns:
        str: a rendered filelists.xml snippet

    """
    context = Context({'pkgid': checksum})
    return Template(template).render(context)


# Additional utils (not from pulp2) #

def render_metadata(pkg, md_type):
    """
    Render a requested metadata type for a package.

    Args:
        pkg(pulp_2to3_migration.app.plugin.rpm.pulp_2to3_models.Pulp2Rpm): a package to render
                                                                           metadata for
        md_type(str): type of metadata: 'primary', 'other' or 'filelists'

    """
    if md_type not in METADATA_TYPES:
        return

    xml_template = pkg.repodata[md_type]
    if md_type == 'primary':
        return render_primary(xml_template, pkg.checksum, pkg.checksumtype)
    elif md_type == 'other':
        return render_other(xml_template, pkg.checksum)
    elif md_type == 'filelists':
        return render_filelists(xml_template, pkg.checksum)


def get_cr_obj(pkg):
    """
    Convert a pulp 2 package object into a createrepo_c one.

    Args:
        pkg(pulp_2to3_migration.app.plugin.rpm.pulp2_models.Pulp2Rpm): pulp 2 package to convert

    Returns:
        createrepo_c.Package: createrepo_c Package object for the requested package

    """
    primary_xml = render_metadata(pkg, 'primary')
    other_xml = render_metadata(pkg, 'other')
    filelists_xml = render_metadata(pkg, 'filelists')

    cr_obj = parse_repodata(primary_xml, other_xml, filelists_xml)
    return cr_obj


def parse_repodata(primary_xml, filelists_xml, other_xml):
    """
    Parse repodata to extract package info.
    Args:
        primary_xml (str): a string containing contents of primary.xml
        filelists_xml (str): a string containing contents of filelists.xml
        other_xml (str): a string containing contents of other.xml
    Returns:
        dict: createrepo_c package objects with the pkgId as a key
    """
    packages = {}

    def pkgcb(pkg):
        """
        A callback which is used when a whole package entry in xml is parsed.
        Args:
            pkg(preaterepo_c.Package): a parsed metadata for a package
        """
        packages[pkg.pkgId] = pkg

    def newpkgcb(pkgId, name, arch):
        """
        A callback which is used when a new package entry is encountered.
        Only opening <package> element is parsed at that moment.
        This function has to return a package which parsed data will be added to
        or None if a package should be skipped.
        pkgId, name and arch of a package can be used to skip further parsing. Available
        only for filelists.xml and other.xml.
        Args:
            pkgId(str): pkgId of a package
            name(str): name of a package
            arch(str): arch of a package
        Returns:
            createrepo_c.Package: a package which parsed data should be added to.
            If None is returned, further parsing of a package will be skipped.
        """
        return packages.get(pkgId, None)

    # TODO: handle parsing errors/warnings, warningcb callback can be used below
    cr.xml_parse_primary_snippet(primary_xml, pkgcb=pkgcb, do_files=False)
    cr.xml_parse_filelists_snippet(filelists_xml, newpkgcb=newpkgcb)
    cr.xml_parse_other_snippet(other_xml, newpkgcb=newpkgcb)
    return list(packages.values())[0]


def decompress_repodata(compressed_repodata):
    """
    Decompress repodata.
    Args:
        compressed_repodata(dict): compressed repodata with the primary/filelists/other as a key
    Returns:
        dict: decompressed repodata with the primary/filelists/other as a key

    """

    decompressed_repodata = {}
    for name, gzipped_data in compressed_repodata.items():
        decompressed_repodata[name] = gzip.zlib.decompress(
            bytearray(gzipped_data)).decode()
    return decompressed_repodata
