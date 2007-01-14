"""Yet another WSGI micro-framework..."""

import cgi, string, new, sys
from wsgiref.util import shift_path_info, application_uri

__all__ = [
    "HTTP", "validator", "Template", "HTML", "Text", "Page", "Container",
    "Form", "EvalTemplate", "EvalMap", "Method",
]
    
class HTTP(object):
    cls_registry = "http_methods"
    def __init__(self, func):
        self.func = func
    def __get__(self, ob, typ=None):
        if ob is None: return self
        return self.func.__get__(ob,typ)

def validator(func):
    func.cls_registry = "registered_validators"
    return func

text_plain = ('Content-Type', 'text/plain')
text_html  = ('Content-Type', 'text/html')

def get_module():
    return sys._getframe(2).f_globals.get('__name__')














sentinel = object()

class EvalMap(object):
    """Object that translates from getitem->getattr"""

    def __init__(self, ob, extra={}):
        self.ob = ob
        self.extra = dict(extra)    # always copy, to allow mod by listcomps

    def __setitem__(self, key, value):  # needed for listcomp exprs!
        self.extra[key] = value

    def __delitem__(self, key):         # needed for listcomp exprs!
        del self.extra[key]

    def __getitem__(self, key):
        if key.startswith('(?'):
            return eval(key[2:].rstrip('?)').strip(), globals(), self)
        elif key in self.extra:
            return self.extra[key]            
        else:
            ob = getattr(self.ob, key, sentinel)
            if ob is not sentinel:
                return ob
        if key=='self':
            return self
        raise KeyError
           
class EvalTemplate(string.Template):
    idpattern = r'[_a-z][_a-z0-9]*|\(\?[^?]*\?\)'


class Method(object):
    def __init__(self, func):
        self.call = func

    def __get__(self, ob, typ=None):
        if ob is None: return self
        return new.instancemethod(self.call, ob, typ)


class Text(Method):
    """Text template w/string substitution that can be used as a method

    Note: templates cannot be directly invoked from the web unless wrapped in
    HTTP() as a request method like GET or POST.
    """   
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
        return self.template.substitute(EvalMap(page, kw))

    @classmethod
    def fragment(cls, *args, **kw):
        return property(cls(caller = get_module(), *args, **kw).render)

    @classmethod
    def function(cls, *args, **kw):
        return Method(cls(caller = get_module(), *args, **kw).render)

class HTML(Text):
    """HTML template w/string substitution that can be used as a method

    Note: templates cannot be directly invoked from the web unless wrapped in
    HTTP() as a request method like GET or POST.
    """   
    headers = text_html,
    

class Template(HTML):
    """TurboGears/Buffet template that can be used as a method

    Note: templates cannot be directly invoked from the web unless wrapped in
    HTTP() as a request method like GET or POST.
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
        return self.engine.render(EvalMap(page,kw), template=self.template)






class Page:
    """A page with no children"""

    cls_registry = "pages"
    http_methods = []

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

    def __init__(self, environ, start_response):
        self.environ = environ
        self.start_response = start_response
        self.errors = []

    def go(self):
        rm = self.environ['REQUEST_METHOD']
        if rm in self.http_methods:
            return getattr(self, rm)()

        return self._method_not_allowed(
            [('Allow', ', '.join(self.http_methods))]
        )

    @HTTP
    def HEAD(self):
        resp = iter(self.GET())     # this will fail if no GET!
        list(resp)      # questionable hack to exhaust the response
        return resp     # ensure that .close() gets called, if any


    _method_not_allowed = Text(
        "405 Method not allowed", status="405 Method not allowed",
    )

    _redirect = HTML(
        '<html><head>'
        '<meta http-equiv="refresh" content="0;url=$url" />'
        '</head><body><a href="$url">Click here</a></body></html>',
        status='302 Found',
    )    

    def redirect(self, url, ):
        return self._redirect([('Location', url)], url=url)




























class Container(Page):
    """A page that may have children, and delegates to them"""

    def go(self):
        name = shift_path_info(self.environ)
        if name=='':
            # it's us, not our contents, handle normally
            return super(Container, self).go()

        if name is None:
            # They left off the trailing / - redirect so relative URLs will
            # be correct...
            url = application_uri(self.environ)
            if not url.endswith('/'):
                url += '/'
            return self.redirect(url)

        sub_app = self[name]
        if sub_app is not None:
            return sub_app(self.environ, self.start_response)

        return self.not_found()

    not_found = Text(
        "404 not found\n"
        "You deserve a kinder note\n"
        "Than this web haiku!\n",
        status  = '404 Not Found',
    )

    def __getitem__(self, key):
        if key in self.pages:
            return getattr(self, key)








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

    GET = HTTP(succeed) # you should replace this with the form's template

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
    
    fail = HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>What is your favorite animal ?</title></head>
<body>
 $show_errors
 <form method="post">
  <table>
   <tr><td>What is your name ?</td>
       <td><input type="text" name="name" value="$name"/></td></tr>
   <tr><td>What is your favorite animal ?</td>
       <td><input type="text" name="animal" value="$animal"/></td></tr>
   <tr><td>What is your email address ?</td>
       <td><input type="text" name="email" value="$email"/></td></tr>
   <tr><td colspan="2"><input type="submit" /></td></tr>
  </table>
 </form>
</body>
</html>
""")
    succeed = Text("Hey Joe!")
    GET = HTTP(fail)

    @validator
    def check_joe(self):
        if self.name!='Joe': self.errors.append("Hey, you're not Joe!")

    errors_found = HTML.fragment(
        "<p>Please correct the following problems:</p>"
        '<ul class="form_errors"><li class="form_error">'
        r'$(? "</li><li class=\"form_error\">".join(errors) ?)'
        '</li></ul>'
    )
    

class TestContainer(Container):

    GET = HTTP(HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Silly test of WebHaiku</title></head>
<body>
    <ul><li><a href="a">Hello world</a></li><li><a href="b">Hello Joe</a></li>
    <li><a href="c">Subcontainer</a></li>
    </ul>
</body></html>"""))

    class a(Page):
        GET = HTTP(Text("Hello world!"))

    b = TestForm

    c = Container   # placeholder

TestContainer.c = TestContainer     # allow some depth to the test...




















