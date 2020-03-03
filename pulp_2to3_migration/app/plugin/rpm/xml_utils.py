"""
To render xml snippets for RPM.

Mostly ported from Pulp 2.

"""
import gzip
import re
import tempfile

from collections import namedtuple

from django.template import (
    Context,
    Template,
)
from django.template.defaulttags import TemplateTagNode

from pulp_rpm.app.tasks.synchronizing import RpmFirstStage


ESCAPE_TEMPLATE_VARS_TAGS = {
    'primary': ('description', 'summary'),
    'other': ('changelog',)}
METADATA_TYPES = ('primary', 'other', 'filelists')

XmlElement = namedtuple('xml_element', ['start', 'end'])
FAKE_XML = {
    'primary': XmlElement('<?xml version="1.0" encoding="UTF-8"?><metadata packages="1" '
                          'xmlns="http://linux.duke.edu/metadata/common" '
                          'xmlns:rpm="http://linux.duke.edu/metadata/rpm">',
                          '</metadata>'),
    'other': XmlElement('<otherdata xmlns="http://linux.duke.edu/metadata/other" packages="1">',
                        '</otherdata>'),
    'filelists': XmlElement('<filelists xmlns="http://linux.duke.edu/metadata/filelists" '
                            'packages="1">',
                            '</filelists>')
}


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
    return re.sub(symbols_pattern,
                  lambda mobj: '{%% templatetag %s %%}' % templatetag_map[mobj.group(1)],
                  template)


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


def _render(template, context):
    """
    Given a template as a string and a Context object, returns the rendered result as a string.

    Args:
        template(str): a django template
        context(django.template.Context): the required context for the template

    Returns:
        str: the result of rendering the template with the context

    """
    t = Template(template)
    rendered = t.render(context)
    return rendered


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
    context = Context({'checksum': checksum,
                       'checksumtype': checksumtype})
    return _render(template, context)


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
    return _render(template, context)


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
    return _render(template, context)


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

    xml_template = gzip.zlib.decompress(bytearray(pkg.repodata[md_type])).decode()
    if md_type == 'primary':
        return render_primary(xml_template, pkg.checksum, pkg.checksumtype)
    elif md_type == 'other':
        return render_other(xml_template, pkg.checksum)
    elif md_type == 'filelists':
        return render_filelists(xml_template, pkg.checksum)


async def get_cr_obj(pkg):
    """
    Convert a pulp 2 package object into a createrepo_c one.

    Args:
        pkg(pulp_2to3_migration.app.plugin.rpm.pulp2_models.Pulp2Rpm): pulp 2 package to convert

    Returns:
        createrepo_c.Package: createrepo_c Package object for the requested package

    """
    filenames = {}
    with tempfile.TemporaryDirectory() as dir:
        for md_type in METADATA_TYPES:
            with tempfile.NamedTemporaryFile(delete=False, dir=dir) as fd:
                xml_snippet = render_metadata(pkg, md_type)
                fake_element = FAKE_XML[md_type]
                final_xml = fake_element.start + xml_snippet + fake_element.end
                fd.write(final_xml.encode())
                filenames[md_type] = fd.name

        packages = await RpmFirstStage.parse_repodata(filenames['primary'], filenames['other'],
                                                      filenames['filelists'])
        # there is always only one package
        cr_obj = list(packages.values())[0]

    return cr_obj
