import sys
import pkg_resources
from cStringIO import StringIO
from textwrap import TextWrapper

from paste.script.command import get_commands

from templer.core.base import wrap_help_paras
from templer.core.ui import list_sorted_templates


def get_templer_packages():
    """return a list of the templer namespace packages currently installed"""
    templer_packages = [k for k in pkg_resources.working_set.by_key.keys()\
        if 'templer' in k.lower()]

    return templer_packages


USAGE = """
Usage:

    %(script_name)s <template> <output-name> [var1=value] ... [varN=value]

    %(script_name)s --help                Full help
    %(script_name)s --list                List template verbosely, with details
    %(script_name)s --make-config-file    Output %(dotfile_name)s prefs file
    %(script_name)s --version             Print versions of installed templer
                                          packages

%(templates)s
Warning:  use of the --svn-repository argument is not allowed with this script

For further help information, please invoke this script with the
option "--help".
"""


DESCRIPTION = """
This script allows you to create basic skeletons for plone and zope
products and buildouts based on best-practice templates.

It is a wrapper around PasteScript ("paster"), providing an easier
syntax for invoking and better help.


Invoking this script
--------------------

Basic usage::

    %(script_name)s <template>

(To get a list of the templates, run the script without any arguments;
for a verbose list with full descriptions, run ``%(script_name)s --list``)

For example::

    %(script_name)s archetype

To create an Archetypes-based product for Plone. This will prompt you
for the name of your product, and for other information about it.

If you to specify your output name (resulting product, egg, or buildout,
depending on the template being used), you can also do so::

    %(script_name)s <template> <output-name>

For example::

    %(script_name)s archetype Products.Example

In addition, you can pass variables to this that would be requested
by that template, and these will then be used. This is an advanced
feature mostly useful for scripted use of this::

    %(script_name)s archetype Products.Example author_email=joel@joelburton.com

(You can specify as many of these as you want, in name=value pairs.
To get the list of variables that a template expects, you can ask for
this with ``%(script_name)s  <template> --list-variables``).


Interactive Help
----------------

While being prompted on each question, you can enter with a single
question mark to receive interactive help for that question.

For example::

  Description (One-line description of the project) ['']: ?

  |  This should be a single-line description of your project. It will
  |  be used in the egg's setup.py, and, for Zope/Plone projects, may be
  |  used in the GenericSetup profile description.


Providing defaults
------------------

It is also possible to set up default values to be used for any template by
creating a file called ``.zopeskel`` in your home directory. This file
should be in INI format.

For example, our ``$HOME/.zopeskel`` could contain::

    [DEFAULT]
    author_email = joel@joelburton.com
    license_name = GPL
    master_keywords = my common keywords here

    [plone3_theme]
    empty_styles = False
    license_name = BSD
    keywords = %%(master_keywords)s additional keywords

You can generate a starter .zopeskel file by running this script with
the --make-config-file option. This output can be redirected into
your ``.zopeskel`` file::

    %(script_name)s --make-config-file > /path/to/home/.zopeskel

Notes:

1) "empty_styles" applies only to themes; we can make this setting
   in the template-specific section of this file. This setting will
   not be used for other templates.

2) For a common setting, like our email address, we can set this in
   a section called DEFAULT; settings made in this section are used
   for all templates.

3) We can make a setting in DEFAULT and then override it for a
   particular template. In this example, we might generally prefer the GPL,
   but issue our themes under the BSD license.

4) You can refer to variables from the same section or from the
   DEFAULT section using Python string formatting. In this example,
   we have a common set of keywords set in DEFAULT and extend it
   for the theming template by referring to the master list.


Differences from the 'paster create' command
--------------------------------------------

1) The --svn-repository argument that can be provided to 'paster create' is
   not allowed when using the %(script_name)s script.  It will raise an error.
   The reasons for this are discussed at length in the zopeskel mailing list
   and in the zopeskel issue tracker:
   http://plone.org/products/zopeskel/issues/34
   http://plone.org/products/zopeskel/issues/35

   If this argument is desired, the user should revert to calling 'paster
   create' directly.  However, be warned that buildout templates will not work
   with the argument due to assumptions in the base paster code.


Questions
---------

If you have further questions about the usage of bin/%(script_name)s, please
feel free to post your questions to the zopeskel mailing list or jump onto the
plone IRC channel (#plone) at irc.freenode.net.


To see the templates supported, run this script without any options.
For a verbose listing with help, use ``%(script_name)s --list``.
"""


DOT_HELP = {
  0: """
This template expects a project name with no dots in it (a simple
Python package name, like 'foo').
""",
  1: """
This template expects a project name with 1 dot in it (a 'basic
namespace', like 'foo.bar').
""",
  2: """
This template expects a project name with 2 dots in it (a 'nested
namespace', like 'foo.bar.baz').
"""}


DOTFILE_HEADER = """
# This file allows you to set default values for %(script_name)s.
# To set a global default, uncomment any line that looks like:
#    variable_name = Default Value

[DEFAULT]
"""


HELP_PROMPT = """
If at any point, you need additional help for a question, you can enter
'?' and press RETURN.
"""


SVN_WARNING = """
For a number of reasons, the --svn-repository argument is not supported
with the %s script. Try --help for more information.
"""


ID_WARNING = "Not a valid Python dotted name: %s ('%s' is not an identifier)"


class Runner(object):
    """encapsulates command-line interactions

    Override public API methods to change behaviors
    """
    texts = {
        'usage': USAGE,
        'description': DESCRIPTION,
        'dot_help': DOT_HELP,
        'dotfile_header': DOTFILE_HEADER,
        'help_prompt': HELP_PROMPT,
        'svn_warning': SVN_WARNING,
        'id_warning': ID_WARNING,
    }
    name = 'templer'
    dotfile = '.zopeskel'

    def __init__(self, name=None, versions=None, dotfile=None, texts={}):
        """initialize a runner with the given name"""
        if name is not None:
            self.name = name
        # if versions is not passed, default to getting all installed
        # templer packages
        if versions is not None:
            if not isinstance(versions, (list, tuple)):
                versions = [versions, ]
        else:
            versions = self._get_templer_packages()
        self.versions = versions

        if dotfile is not None:
            self.dotfile = dotfile

        if not isinstance(texts, dict):
            raise ValueError("If passed, texts argument must be a dict")
        self.texts.update(texts)

    def __call__(self, argv):
        """command-line interaction and template execution

        argv should be passed in as sys.argv[1:]
        """
        try:
            template_name, output_name, opts = self._process_args(argv)
        except SyntaxError, e:
            self.usage(exit=False)
            msg = "ERROR: There was a problem with your arguments: %s\n"
            print msg % str(e)
            raise
            sys.exit(1)

        rez = pkg_resources.iter_entry_points(
                'paste.paster_create_template',
                template_name)
        rez = list(rez)
        if not rez:
            self.usage(exit=False)
            print "ERROR: No such template: %s\n" % template_name
            sys.exit(1)

        template = rez[0].load()
        print "\n%s: %s" % (template_name, template.summary)
        help = getattr(template, 'help', None)
        if help:
            print template.help

        create = get_commands()['create'].load()
        command = create('create')

        # allow special runner processing to be bypassed in case of certain
        # standard paster args
        short_circuit = False
        special_args = []
        if '--list-variables' in argv:
            special_args.append('--list-variables')
            short_circuit = True
            output_name = None

        if not short_circuit:
            if output_name:
                try:
                    self._checkdots(template, output_name)
                except ValueError, e:
                    print "ERROR: %s\n" % str(e)
                    raise
                    sys.exit(1)
            else:
                ndots = getattr(template, 'ndots', None)
                help = DOT_HELP.get(ndots)
                while True:
                    if help:
                        print help
                    try:
                        challenge = "Enter project name (or q to quit)"
                        output_name = command.challenge(challenge)
                        if output_name == 'q':
                            print "\n\nExiting...\n"
                            sys.exit(0)
                        self._checkdots(template, output_name)
                    except ValueError, e:
                        print "\nERROR: %s" % e
                        raise
                    else:
                        break

            print self.texts['help_prompt']

        optslist = ['%s=%s' % (k, v) for k, v in opts.items()]
        if output_name is not None:
            optslist.insert(0, output_name)
        try:
            command.run(['-q', '-t', template_name] + optslist + special_args)
        except KeyboardInterrupt:
            print "\n\nExiting...\n"
            sys.exit(0)
        except Exception, e:
            print "\nERROR: %s\n" % str(e)
            raise
            sys.exit(1)
        sys.exit(0)

    # Public API methods, can be overridden by templer-based applications
    def show_help(self):
        """display help text"""
        print self.texts['description'] % {'script_name': self.name}
        sys.exit(0)

    def generate_dotfile(self):
        """generate a dotfile to hold default values

        method must exit by raising error or calling sys.exit
        """

        cats = list_sorted_templates()
        print self.texts['dotfile_header'] % {'script_name': self.name}
        for temp in sum(cats.values(), []):
            print "\n[%(name)s]\n" % temp
            tempc = temp['entry'].load()
            for var in tempc.vars:
                if hasattr(var, 'pretty_description'):
                    print "# %s" % var.pretty_description()
                print "# %s = %s\n" % (var.name, var.default)
        sys.exit(0)

    def list_verbose(self):
        """list available templates and their help text

        method must exit by raising error or calling sys.exit
        """
        textwrapper = TextWrapper(
            initial_indent="   ", subsequent_indent="   ")
        cats = list_sorted_templates()

        for title, items in cats.items():
            print "\n"+ title
            print "-" * len(title)
            for temp in items:
                print "\n%s: %s\n" % (temp['name'], temp['summary'])
                if temp['help']:
                    wrap_help_paras(textwrapper, temp['help'])
        print
        sys.exit(0)

    def show_version(self):
        """show installed version of packages listed in self.versions

        method must exit by raising error or calling sys.exit
        """
        version_info = self._get_version_info()
        print self._format_version_info(
            version_info, "Installed Templer Packages")
        sys.exit(0)

    def usage(self, exit=True):
        """print usage message

        method must exit by raising error or calling sys.exit
        """
        templates = self._list_printable_templates()
        print self.texts['usage'] % {'templates': templates,
                                     'script_name': self.name,
                                     'dotfile_name': self.dotfile}
        if exit:
            sys.exit(0)

    # Private API supporting command-line flags
    # should not need to be changed by templer-based applications
    def _get_templer_packages(self):
        """return a list of the templer namespace packages currently installed
        """
        templer_packages = [k for k in pkg_resources.working_set.by_key.keys()\
            if 'templer' in k.lower()]
        return templer_packages

    def _get_version_info(self):
        """provided a list of distribution names, return version info for them
        """
        version_info = []
        for package_name in self.versions:
            try:
                dist = pkg_resources.get_distribution(package_name)
                version_info.append((dist.project_name, dist.version, ))
            except pkg_resources.DistributionNotFound:
                version_info.append((package_name, 'Not Installed'))
        return version_info

    def _format_version_info(self, version_info, header=None):
        """created a printable string of installed package version numbers
        """
        s = StringIO()
        maxpkg = max([len(vi[0]) for vi in version_info])
        maxver = max([len(vi[1]) for vi in version_info])
        if header is not None:
            print >>s, "\n| %s" % header
            print >>s, "+" + ("-" * (maxpkg + maxver + 3))
        for vi in version_info:
            padding = maxpkg - len(vi[0])
            values = [vi[0], ' ' * padding, vi[1]]
            print >>s, "| %s:%s %s" % tuple(values)
        s.seek(0)
        return s.read()

    def _list_printable_templates(self):
        """
        Printable list of all templates, sorted into categories.
        """
        s = StringIO()
        cats = list_sorted_templates()
        templates = sum(cats.values(), [])   # flatten into single list
        max_name = max([len(x['name']) for x in templates])
        for title, items in cats.items():
            print >>s, "\n%s\n" % title
            for entry in items:
                print >>s, "|  %s:%s %s\n" % (
                     entry['name'],
                    ' '*(max_name-len(entry['name'])),
                    entry['summary']),
        s.seek(0)
        return s.read()

    # Private API supporting the template run itself
    # these methods should not need modification by templer-based applications
    def _process_args(self, args):
        """return a tuple of template_name, output_name and everything else

        everything else will be returned as a dictionary of key/value pairs
        """
        try:
            template_name = args.pop(0)
        except IndexError:
            raise SyntaxError('No template name provided')
        output_name = None
        others = {}
        for arg in args:
            eq_index = arg.find('=')
            if eq_index == -1 and not output_name:
                output_name = arg
            elif eq_index > 0:
                key, val = arg.split('=')
                # the --svn-repository argument to paster does some things that
                # cause it to be pretty much incompatible with zopeskel. See
                # the following zopeskel issues:
                #     http://plone.org/products/zopeskel/issues/35
                #     http://plone.org/products/zopeskel/issues/34
                # For this reason, we are going to disallow using the
                # --svn-repository argument when using the zopeskel wrapper.
                #
                # Those who wish to use it can still do so by going back to
                # paster, with the caveat that there are some templates
                # (particularly the buildout ones) for which the argument will
                # always throw errors (at least until the problems are fixed
                # upstream in paster itself).
                if 'svn-repository' in key:
                    raise SyntaxError(self.texts['svn_warning'] % self.name)
                others[key] = val
            else:
                raise SyntaxError(arg)

        return template_name, output_name, others

    def _checkdots(self, template, name):
        """Check if project name appears legal, given template requirements.

        Templates can provide the number of namespaces they expect (provided
        in 'ndots' attributes for number-of-dots in name). This method
        validates that the provided project name has the expected number of
        namespaces and that each part is a legal Python identifier.
        """

        cdots = name.count(".")
        if cdots > 5:
            raise ValueError("Five dots should be more than enough, "
                             "no black hole please")


templer_runner = Runner()


def run(runner=templer_runner):

    if "--help" in sys.argv:
        runner.show_help()

    if "--make-config-file" in sys.argv:
        runner.generate_dotfile()

    if "--list" in sys.argv:
        runner.list_verbose()

    if "--version" in sys.argv:
        runner.show_version()

    if len(sys.argv) == 1:
        runner.usage()

    args = sys.argv[1:]
    runner(args)
