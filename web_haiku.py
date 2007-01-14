"""Yet another WSGI micro-framework..."""

import cgi, string, new, sys
from wsgiref.util import shift_path_info, application_uri

__all__ = [
    "Page", "Form", "validator", "HTML", "Text", "Template", "HTTP",    
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


def validator(func):
    """Decorator that marks an object as a registered validator"""
    func.cls_registry = "registered_validators"
    return func

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

    def __getitem__(self, key):
        if key.startswith('(?'):
            return eval(
                key[2:].rstrip(')').rstrip('?').strip(),
                sys.modules[self.module].__dict__, self
            )
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
        raise KeyError
           
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

    def invoke_method(self):
        rm = self.environ['REQUEST_METHOD']
        if rm=='GET' and self.body is not None:
            return self.body()
        if rm=='HEAD' or rm in self.http_methods:
            return getattr(self, rm)()
        return self.METHOD_NOT_ALLOWED(
            [('Allow', ', '.join(self.http_methods))]
        )

    def HEAD(self):
        environ['REQUEST_METHOD'] = 'GET'
        resp = iter(self.invoke_method())   # forward to 'GET'
        list(resp)      # questionable hack to exhaust the response
        return resp     # ensure that .close() gets called, if any

    def go(self):
        name = shift_path_info(self.environ)
        if name:
            return self.handle_child(name)

        url = application_uri(self.environ).rstrip('/')
        leaf = not self.sub_pages and type(self).handle_child == Page.handle_child

        if name=='':    # trailing /
            if not leaf:            
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





















    db = None   # DBAPI database connection object

    def db_connect(self):
        """Override this in a subclass to return a DBAPI connection object"""
        raise NotImplementedError

    def query(self, *args, **kw):
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















class Form(Page):
    """A page with POST processing, form parsing, validation, etc."""
    registered_validators = []
    data = {}
    defaults = {}
    def get_validators(self):
        return self.registered_validators

    def validate(self):
        for k in self.get_validators():
            response = getattr(self,k)()
            if response:
                return response

    def __getattr__(self, name):
        if not name.startswith('__'):
            try:
                return self.data[name].value
            except KeyError:
                if name in self.defaults:
                    return self.defaults[name]
        raise AttributeError(name)

    succeed = Text("Oops.  Someone forgot to create a form or method here.")

    body = succeed  # you should replace this with the form's template

    def parse(self):
        self.data = cgi.FieldStorage(
            self.environ['wsgi.input'], environ=self.environ
        )

    errors_found = HTML.fragment(
        '<ul class="form_errors"><li class="form_error">'
        r'$(? "</li><li class=\"form_error\">".join(errors) ?)'
        '</li></ul>'
    )

    show_errors = property(lambda self: self.errors and self.errors_found or '')


    @HTTP
    def POST(self):
        self.parse()
        response = self.validate()
        if response:
            return response
        elif self.errors:
            return self.fail()
        else:
            return self.succeed()

    # A miserably inadequate attempt at a decent UI...  
    fail = HTML(
        "<html><head>"
        "<title>Sorry, we couldn't process your request</title></head>\n<body>"
        "<h2>Sorry, we couldn't process your request</h2>\n"
        "<p>We encountered some difficulties with your input:</p>"
        "$errors_found\n"
        "<p>If you would please use your browser's BACK button to go back and "
        "correct these problems, we'd appreciate it.  Thanks for your help!"
        "</p></body>"
    )



















class TestForm(Form):
    """A stupid example to test the framework"""

    defaults = dict(name='Joey', animal='Dog', email='joe@dog.com')
    
    body = fail = HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>What is your favorite animal ?</title></head>
<body>
 $show_errors
 <form method="post">
  <table>
   <tr><td>What is your name ?</td>
       <td><input type="text" name="name" value="$(?cgi.escape(name)?)"/></td></tr>
   <tr><td>What is your favorite animal ?</td>
       <td><input type="text" name="animal" value="$(?cgi.escape(animal)?)"/></td></tr>
   <tr><td>What is your email address ?</td>
       <td><input type="text" name="email" value="$(?cgi.escape(email)?)"/></td></tr>
   <tr><td colspan="2"><input type="submit" /></td></tr>
  </table>
 </form>
</body>
</html>
""")
    succeed = Text("Hey Joe!")

    @validator
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























