"""Yet another WSGI micro-framework..."""

import cgi, string, new, sys
from wsgiref.util import shift_path_info, application_uri

__all__ = [
    "Page", "form_handler", "HTML", "Text", "Template", "HTTP", "test",
    "EvalTemplate", "EvalMap", "Method",
]

class Method(object):
    """Turn any object into a method"""
    def __init__(self, func):
        self.call = func

    def __get__(self, ob, typ=None):
        if ob is None: return self
        return new.instancemethod(self.call, ob, typ)

class HTTP(Method):
    """Wrapper/decorator that marks an object as an HTTP method"""

    cls_registry = "http_methods"

def form_handler(arg):
    """Decorator that marks an object as a registered validator"""
    def decorator(func):
        func.cls_registry = "form_handlers"
        func.priority = priority, func.__name__
        return func
    if isinstance(arg, type(form_handler)):
        priority = 0
        return decorator(arg)
    return decorator

text_plain = ('Content-Type', 'text/plain')
text_html  = ('Content-Type', 'text/html')

def get_module():
    return sys._getframe(2).f_globals.get('__name__', __name__)

sentinel = object()

class EvalMap(object):
    """Object that translates from getitem->getattr"""

    def __init__(self, page, extra={}, module=__name__):
        self.page = page
        self.extra = dict(extra)    # always copy, to allow mod by listcomps
        self.module = module

    def __setitem__(self, key, value):  # needed for listcomp exprs!
        self.extra[key] = value

    def __delitem__(self, key):         # needed for listcomp exprs!
        del self.extra[key]

    def __contains__(self, key):
        try: self[key]
        except KeyError: return False
        return True

    def __getitem__(self, key):
        if key.startswith('(?'):
            return eval(key[2:].rstrip(')').rstrip('?').strip(),
                        sys.modules[self.module].__dict__, self)
        elif key in self.extra:
            return self.extra[key]
        else:
            ob = getattr(self.page, key, sentinel)
            if ob is not sentinel:
                return ob
            g = sys.modules[self.module].__dict__
            if key in g:
                return g[key]
        if key=='self':
            return self
        raise KeyError(key)

class EvalTemplate(string.Template):
    idpattern = r'[_a-z][_a-z0-9]*|\(\?[^?]*\?\)'

class Text(Method):
    """Text template w/string substitution that can be used as a method

    Note: templates cannot be directly invoked from the web unless they
    are created with Text.page() or Text.http_method(), or used as a Page's
    ``body`` attribute.
    """

    cls_registry = None
    factory = EvalTemplate
    status  = '200 OK'
    headers = text_plain,
    resource = caller = None

    def __init__(self, *args, **kw):
        kw.setdefault('caller', get_module())
        for k, v in kw.items():
            if hasattr(type(self),k):
                setattr(self, k, v)
                del kw[k]
        if self.resource:
            self.options = kw
        else:
            self.template = self.factory(*args, **kw)

    def call(self, page, extra_headers = [], **kw):
        content = self.render(page, kw)
        headers = list(self.headers) + extra_headers
        headers.append(('Content-Length',str(len(content))))
        page.start_response(self.status, headers)
        return [content]

    def render(self, page, kw={}):
        if self.resource:
             from pkg_resources import resource_string
             body = resource_string(self.caller, self.resource)
             self.template = self.factory(body, **self.options)
             self.resource = None
        return self.template.substitute(EvalMap(page, kw, self.caller))


    @classmethod
    def fragment(cls, *args, **kw):
        """Template property that returns its rendered body"""
        return property(cls(caller = get_module(), *args, **kw).render)

    @classmethod
    def http_method(cls, *args, **kw):
        """Template that can be used as an HTTP method (GET, POST, PUT, etc.)"""
        return cls(
            caller=get_module(), cls_registry='http_methods', *args, **kw
        )

    @classmethod
    def method(cls, *args, **kw):
        """Template method that can be called with keyword arguments"""
        return Method(cls(caller = get_module(), *args, **kw).render)

    @classmethod
    def page(cls, *args, **kw):
        """Template sub-page (returns a Page subclass w/template as its body)

        If you supply a `type` keyword argument, that type is used as the base
        class for the page.  The other arguments are used to create the
        template to be used as the returned class' ``body`` attribute.
        """
        caller = get_module()
        class _Page(kw.get('type',Page)):
            body = cls(caller=caller, *args, **kw)
        return _Page












class HTML(Text):
    """HTML template w/string substitution that can be used as a method

    Note: templates cannot be directly invoked from the web unless they
    are created with HTML.page() or HTML.http_method(), or used as a Page's
    ``body`` attribute.
    """
    headers = text_html,


class Template(HTML):
    """TurboGears/Buffet template that can be used as a method

    Note: templates cannot be directly invoked from the web unless they
    are created with Template.page() or Template.http_method(), or used as a
    Page's ``body`` attribute.
    """

    engine = None
    resource = property(lambda self:None)   # resources can't be used for this

    def factory(self, templatename, **options):
        engine, name = templatename.split(':', 1)
        from pkg_resources import iter_entry_points
        for ep in iter_entry_points('python.templating.engines',engine):
            self.engine = ep.load()()
            break
        else:
            raise RuntimeError("Template engine %r is not installed" % (engine,))
        return name

    def render(self, page, kw={}):
        return self.engine.render(
            EvalMap(page,kw,self.caller), template=self.template
        )






class Page(object):
    """A generic web location"""

    cls_registry = "sub_pages"
    http_methods = []
    sub_pages = []
    body = None

    class __metaclass__(type):
        def __init__(cls, name, bases, cdict):
            for k in dir(cls):
                v = getattr(cls, k)
                reg = getattr(v, 'cls_registry', None)
                if reg:
                    d = cdict.setdefault(reg,[])
                    d.append(k)
                    setattr(cls, reg, d)

        def __call__(cls, *args, **kw):
            self = type.__call__(cls, *args, **kw)
            return self.go()

    def __init__(self, environ, start_response, **kw):
        self.environ = environ
        self.start_response = start_response
        cls = type(self)
        for k, v in kw.items():
            getattr(cls,k)  # AttributeError here means bad keyword arg
            setattr(self,k,v)
        self.setup()    # perform any dynamic initialization











    def HEAD(self):
        def write(txt):
            sr.length += len(txt)

        def sr(status, headers, exc_info=None):
            if exc_info:
                if sr.length:
                    try:
                        raise exc_info[0], exc_info[1], exc_info[2]
                    finally:
                        exc_info = None
            elif sr.status is not None:
                raise AssertionError("Headers already set!")

            sr.status,sr.headers,sr.exc_info = status,Headers(headers),exc_info
            return write

        from wsgiref.headers import Headers
        sr.length = 0
        sr.status, sr.headers, sr.exc_info = None, (), None
        old_sr = self.start_response
        self.start_response = sr
        self.environ['REQUEST_METHOD'] = 'GET'

        try:
            resp = self.invoke_method()   # forward to 'GET'
            if 'Content-Length' not in sr.headers:
                for chunk in resp:
                    sr.length += len(chunk)
                    if 'Content-Length' in sr.headers:
                        break
            if hasattr(resp,'close'):
                resp.close()
            if 'Content-Length' not in sr.headers:
                sr.headers['Content-Length'] = str(sr.length)

            old_sr(sr.status, sr.headers.items(), sr.exc_info)
            return ['']
        finally:
            sr.args = exc_info = None  # clean up exc_info, if still present

    def go(self):
        self.URL = application_uri(self.environ)
        name = shift_path_info(self.environ)
        if name:
            return self.handle_child(name)

        url = self.URL.rstrip('/')
        leaf = not self.sub_pages and type(self).handle_child == Page.handle_child

        if name=='':    # trailing /
            if not leaf or self.environ.get('SCRIPT_NAME')=='/':
                return self.invoke_method()
        elif name is None:    # no trailing /
            if leaf:
                return self.invoke_method()
            url += '/'  # add the trailing /
        return self.redirect(url)

    def handle_child(self, name):
        if name in self.sub_pages:
            return getattr(self, name)(
                self.environ, self.start_response, parent=self
            )
        return self.NOT_FOUND()

    def redirect(self, url):
        return self.REDIRECT_TO([('Location', url)], url=url)

    def setup(self):
        self.errors = []
        self.db = getattr(self.parent, 'db', None)

    parent = None








    def invoke_method(self):
        rm = self.environ['REQUEST_METHOD']
        if rm=='HEAD' or rm in self.http_methods:
            return getattr(self, rm)()
        elif rm=='GET' and self.body is not None:
            return self.body()
        elif rm=='POST' and self.form_handlers:
            return self.POST()

        methods = set(self.http_methods)    # Compute available methods
        if self.body is not None:
            methods.add('GET')
        if 'GET' in methods:
            methods.add('HEAD')
        if self.form_handlers:
            methods.add('POST')

        return self.METHOD_NOT_ALLOWED([('Allow', ', '.join(methods))])

    METHOD_NOT_ALLOWED = Text(
        "Excellent method!\n"
        "Alas, my response must be:\n"
        '"I cannot comply."',
        status="405 Method not allowed",
    )

    REDIRECT_TO = HTML(
        '<html><head>'
        '<meta http-equiv="refresh" content="0;url=$url" />'
        '</head><body><a href="$url">Click here</a></body></html>',
        status='302 Found',
    )

    NOT_FOUND = Text(
        "404 not found\n"
        "You deserve a kinder note\n"
        "Than this web haiku!\n",
        status  = '404 Not Found',
    )


    form_handlers = []
    form_parsed = False
    form_data = ()
    form_defaults = {}
    escape = staticmethod(cgi.escape)

    def get_handlers(self):
        handlers = [getattr(self,k) for k in self.form_handlers]
        handlers.sort(key=lambda h: h.priority)
        return handlers

    def __getattr__(self, name):
        """Dynamic attributes from form_data and defaults"""
        if name in self.form_defaults:  # form vars must be explicitly listed
            if name in self.form_data:
                return self.form_data[name].value
            return self.form_defaults[name]
        raise AttributeError(name)

    def parse_form(self):
        """Ensure that self.form_data contains a FieldStorage, and return it"""
        if not self.form_parsed:
            self.form_data = cgi.FieldStorage(
                self.environ['wsgi.input'], environ=self.environ
            )
            self.form_parsed = True
        return self.form_data

    def POST(self):
        self.parse_form()
        for handler in self.get_handlers():
            response = handler()
            if response:
                return response

        if self.errors:
            return self.form_failure()
        else:
            return self.form_success()


    # A miserably inadequate attempt at a decent UI...

    errors_found = HTML.fragment(
        '<ul class="form_errors"><li class="form_error">'
        r'$(? "</li><li class=\"form_error\">".join(errors) ?)'
        '</li></ul>'
    )

    show_errors = property(lambda self: self.errors and self.errors_found or '')

    form_failure = HTML(
        "<html><head>"
        "<title>Sorry, we couldn't process your request</title></head>\n<body>"
        "<h2>Sorry, we couldn't process your request</h2>\n"
        "<p>We encountered some difficulties with your input:</p>"
        "$errors_found\n"
        "<p>If you would please use your browser's BACK button to go back and "
        "correct these problems, we'd appreciate it.  Thanks for your help!"
        "</p></body>"
    )


    form_success = Text(
        "Oops.  Someone forgot to create a template or method here."
    )
















    db = None   # DBAPI database connection object

    def db_connect(self):
        """Override this in a subclass to return a DBAPI connection object"""
        raise NotImplementedError

    def cursor(self, *args, **kw):
        """Create and return a cursor (after optionally running a query on it)

        If positional arguments are supplied, they're passed to the cursor's
        ``execute()`` method.  If keyword arguments are supplied, they are
        used to set cursor attributes prior to the ``execute()`` (if
        applicable).
        """
        db = self.db
        if db is None:
            db = self.db = self.db_connect()

        cursor = db.cursor()
        for k, v in kw.items():
            setattr(cursor, k, v)

        if args:
            cursor.execute(*args)

        return cursor

    def query(self, *args, **kw):
        csr = self.cursor(*args, **kw)
        return (Row(csr,r) for rows in iter(csr.fetchmany,[]) for r in rows)


class Row(object):
    """Easy-access dict/object wrapper for DBAPI row tuples"""

    def __init__(self, cursor, row):
        self.__dict__ = dict(zip([d[0]for d in cursor.description], row))




def test(app, environ={}, form={}, **kw):
    """Print the output of a WSGI app

    Runs `app` as a WSGI application and prints its output.  If an untrapped
    error occurs in `app`, it drops into the ``pdb`` debugger's post-mortem
    debug shell (using ``sys.__stdout__`` if ``sys.stdout`` has been replaced).

    Any keyword arguments are added to the environment used to run `app`.  If
    a keyword argument begins with ``wsgi_``, the ``_`` is replaced with a
    ``.``, so that you can set e.g. ``wsgi.multithread`` using a
    ``wsgi_multithread`` keyword argument.

    If a non-empty `form` dictionary is provided, it is treated as a collection
    of fields for a form ``POST``. The ``REQUEST_METHOD`` will default to
    ``POST``, and the default ``CONTENT_LENGTH``, ``CONTENT_TYPE``, and
    ``wsgi.input`` values will be appropriately set (but can still be
    overridden by explicit keyword arguments or the `environ` argument).

    Any `form` values that are not instances of ``basestring`` are assumed to
    be *sequences* of values, and will result in multiple name/value pairs
    being added to the encoded data sent to the application.

    Any WSGI-required variables that are not specified by `environ`, `form`, or
    keyword arguments, are initialized to default values using the
    ``wsgiref.util.setup_testing_defaults()`` function.
    """

    from wsgiref.util import setup_testing_defaults
    from wsgiref.handlers import SimpleHandler
    from StringIO import StringIO
    from urllib import quote_plus

    environ = environ.copy()
    for k, v in kw.items():
        if k.startswith('wsgi_'):
            environ[k.replace('_','.',1)] = v
        else:
            environ[k] = v



    if form:
        encoded = []
        for k, v in form.items():
            if isinstance(v,basestring):
                v = [v]
            for v in v:
                encoded.append('%s=%s' % (quote_plus(k), quote_plus(v)))
        encoded = '&'.join(encoded)
        environ.setdefault('wsgi.input', StringIO(encoded))
        environ.setdefault('CONTENT_LENGTH', str(len(encoded)))
        environ.setdefault('CONTENT_TYPE', 'application/x-www-form-urlencoded')
        environ.setdefault('REQUEST_METHOD', 'POST')

    setup_testing_defaults(environ)
    stdout = StringIO()
    stderr = environ['wsgi.errors']

    def wrapper(env, start):
        try:
            return app(env, start)
        except:
            stdout = sys.stdout
            try:
                if stdout is not sys.__stdout__:
                    sys.stdout = sys.__stdout__
                import pdb
                pdb.post_mortem(sys.exc_info()[2])
            finally:
                sys.stdout = stdout
            raise

    SimpleHandler(
        environ['wsgi.input'], stdout, stderr, environ,
        environ['wsgi.multithread'], environ['wsgi.multiprocess']
    ).run(wrapper)
    print stdout.getvalue().replace('\r\n','\n')
    if stderr.getvalue():
        print "--- Log Output ---"
        print stderr.getvalue().replace('\r\n','\n')


class TestForm(Page):
    """A stupid example to test the framework"""

    form_defaults = dict(name='Joey', animal='Dog', email='joe@dog.com')

    body = form_failure = HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>What is your favorite animal ?</title></head>
<body>
 $show_errors
 <form method="post">
  <table>
   <tr><td>What is your name ?</td>
       <td><input type="text" name="name" value="$(?escape(name)?)"/></td></tr>
   <tr><td>What is your favorite animal ?</td>
       <td><input type="text" name="animal" value="$(?escape(animal)?)"/></td></tr>
   <tr><td>What is your email address ?</td>
       <td><input type="text" name="email" value="$(?escape(email)?)"/></td></tr>
   <tr><td colspan="2"><input type="submit" /></td></tr>
  </table>
 </form>
</body>
</html>
""")
    form_success = Text("Hey Joe!")

    @form_handler
    def check_joe(self):
        if self.name!='Joe': self.errors.append("Hey, you're not Joe!")

    errors_found = HTML.fragment(
        "<p>Please correct the following problems:</p>"
        '<ul class="form_errors"><li class="form_error">'
        r'$(? "</li><li class=\"form_error\">".join(errors) ?)'
        '</li></ul>'
    )



class TestContainer(Page):

    body = HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Silly test of WebHaiku</title></head>
<body>
    <ul><li><a href="a">Hello world</a></li><li><a href="b">Hello Joe</a></li>
    <li><a href="c">Subcontainer</a></li>
    </ul>
</body></html>""")

    a = Text.page("Hello world!")
    b = TestForm
    c = Page   # placeholder

TestContainer.c = TestContainer     # allow some depth to the test...


def additional_tests():
    import doctest
    return doctest.DocFileSuite(
        'README.txt',
        optionflags=doctest.ELLIPSIS|doctest.REPORT_ONLY_FIRST_FAILURE,
    )















