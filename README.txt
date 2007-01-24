================================================
Creating quick-and-dirty WSGI Apps with WebHaiku
================================================

WebHaiku is a very small framework for creating quick-and-dirty WSGI apps.  It
is designed for a bare minimum of startup cost and import footprint, so that it
can be used for CGI as well as long-running processes.  It requires either
Python 2.5, or Python 2.4 and the "wsgiref" package from the CheeseShop.  Apart
from ``wsgiref``, it is entirely self-contained, but it can also be used with
TurboGears/Buffet template engine plugins.  (In which case, setuptools and the
appropriate plugin(s) are also required.)


Pages and HTTP Methods
======================

WebHaiku uses classes to represent web-accessible objects::

    >>> from web_haiku import Page, test, HTML

    >>> class HelloPage(Page):
    ...     body = HTML("<h1>Hello, world!</h1>")

The above is a class representing a page whose ``GET`` response will be the
given "Hello world" message.  We can emulate browsing to this page using the
``test()`` function (which incidentally works on any WSGI application, not just
WebHaiku pages!)::

    >>> test(HelloPage)
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    ...
    <h1>Hello, world!</h1>

As you can see, we get back the expected content.  ``HEAD`` requests are also
automatically supported::

    >>> test(HelloPage, REQUEST_METHOD="HEAD")
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    Content-Length: 22
    <BLANKLINE>
    <BLANKLINE>

But ``POST`` requests are not (because we didn't define any form handlers; see
the `Form Handling`_ section, below)::

    >>> test(HelloPage, form={"a":"b"})
    HTTP/1.0 405 Method not allowed
    Date: ...
    Content-Type: text/plain
    Allow: GET, HEAD
    ...
    Excellent method!
    Alas, my response must be:
    "I cannot comply."

Notice that the response contains an automatically-generated ``Allow:`` header,
listing the HTTP methods implemented.  You can add to these allowed methods by
defining ``HTTP`` methods::

    >>> from web_haiku import HTTP
    >>> class PostHello(HelloPage):
    ...     @HTTP
    ...     def POST(self):
    ...         return self.body()  # behave the same as GET

Now ``POST`` works the same as ``GET`` for this page::

    >>> test(PostHello, form={"a":"b"})
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    ...
    <h1>Hello, world!</h1>

And the ``Allow`` for unrecognized methods will now include ``POST``::

    >>> test(PostHello, REQUEST_METHOD='PUT')
    HTTP/1.0 405 Method not allowed
    Date: ...
    Content-Type: text/plain
    Allow: GET, HEAD, POST
    ...
    Excellent method!
    Alas, my response must be:
    "I cannot comply."


Child URLs
==========

By default, pages have no child URLs, and any attempt to access such URLs
results in a 404 response::

    >>> test(HelloPage, PATH_INFO="/x")
    HTTP/1.0 404 Not Found
    Date: ...
    Content-Type: text/plain
    ...
    404 not found
    You deserve a kinder note
    Than this web haiku!
    ...

But you can create subpages using template objects, embedded ``Page`` classes,
or ``@expose`` methods (or `Dynamic Children`_ as described later below)::

    >>> from web_haiku import expose

    >>> class Container(Page):
    ...     x = HTML.page("This is page X")
    ... 
    ...     class y(Page):
    ...         body = HTML("This is page Y")
    ... 
    ...     @expose
    ...     def z(self):
    ...         self.start_response(
    ...             "200 Yeah!", [('Content-type','text/plain')]
    ...         )
    ...         return ['I be da Z!']

    >>> test(Container, PATH_INFO="/x")
    HTTP/1.0 200 OK
    ...
    This is page X

    >>> test(Container, PATH_INFO="/y")
    HTTP/1.0 200 OK
    ...
    This is page Y

    >>> test(Container, PATH_INFO="/z")
    HTTP/1.0 200 Yeah!
    ...
    I be da Z!



Dynamic Children
----------------

You can implement dynamic child URLs by overriding the ``handle_child()``
method of your pages...  XXX




Special URL Handling for Container Pages and Leaf Pages
-------------------------------------------------------

Note that even if a page has children, it must still have a ``body`` of
its own to support ``GET`` operations::

    >>> test(Container)
    HTTP/1.0 405 Method not allowed
    Date: ...
    Content-Type: text/plain
    Allow:...
    ...
    Excellent method!
    Alas, my response must be:
    "I cannot comply."

    >>> Container.body = HTML("This is the container")
    >>> test(Container)
    HTTP/1.0 200 OK
    ...
    This is the container

The URL used to access a page must end with a trailing ``/`` if it is a
container, and it must NOT end with a ``/`` if the page is NOT a container.  If
the URL is incorrect, a redirect is automatically issued::

    >>> test(Container, PATH_INFO="/x/")
    HTTP/1.0 302 Found
    Date: ...
    Content-Type: text/html
    Location: http://127.0.0.1/x
    ...
    ...<meta http-equiv="refresh" content="0;url=http://127.0.0.1/x" />...

Note that this redirection will *NOT* include any form data, so ``PUT`` or
``POST`` bodies are lost!  This redirection is intended to handle user-entered
URLs only.  Query strings, however, are included in the redirection::

    >>> test(Container, PATH_INFO="/x/", QUERY_STRING="y")
    HTTP/1.0 302 Found
    Date: ...
    Content-Type: text/html
    Location: http://127.0.0.1/x?y
    ...
    ...<meta http-equiv="refresh" content="0;url=http://127.0.0.1/x?y" />...


Redirection
===========

    >>> class InlineRedirect(Page):
    ...     def body(self):
    ...         return self.redirect('http://example.com/123')

    >>> test(InlineRedirect)
    HTTP/1.0 302 Found
    Date: ...
    Content-Type: text/html
    Location: http://example.com/123
    ...
    ...<meta http-equiv="refresh" content="0;url=http://example.com/123" />...

    >>> from web_haiku import Redirector
    >>> class TemplateRedirect(Page):
    ...     body = Redirector('http://example.com/$(?environ["REQUEST_METHOD"]?)')

    >>> test(TemplateRedirect)
    HTTP/1.0 302 Found
    Date: ...
    Content-Type: text/html
    Location: http://example.com/GET
    ...
    ...<meta http-equiv="refresh" content="0;url=http://example.com/GET" />...
    

XXX REDIRECT_TO


Form Handling
=============

    >>> from web_haiku import Text, form_handler
    >>> class TestForm(Page):
    ...     """A stupid example to test the framework"""
    ... 
    ...     form_defaults = dict(name='Joey', animal='Dog', email='joe@dog.com')
    ... 
    ...     body = form_failure = HTML("""<?xml version="1.0" encoding="iso-8859-1"?>
    ... <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    ...     "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    ... <html xmlns="http://www.w3.org/1999/xhtml">
    ... <head><title>What is your favorite animal ?</title></head>
    ... <body>
    ...  $show_errors
    ...  <form method="post">
    ...   <table>
    ...    <tr><td>What is your name ?</td>
    ...        <td><input type="text" name="name" value="$(?escape(name)?)"/></td></tr>
    ...    <tr><td>What is your favorite animal ?</td>
    ...        <td><input type="text" name="animal" value="$(?escape(animal)?)"/></td></tr>
    ...    <tr><td>What is your email address ?</td>
    ...        <td><input type="text" name="email" value="$(?escape(email)?)"/></td></tr>
    ...    <tr><td colspan="2"><input type="submit" /></td></tr>
    ...   </table>
    ...  </form>
    ... </body>
    ... </html>""")
    ...     form_success = Text("Hey Joe!")
    ... 
    ...     @form_handler
    ...     def check_joe(self):
    ...         if self.name!='Joe': self.errors.append("Hey, you're not Joe!")
    ... 
    ...     errors_found = HTML.fragment(
    ...         "<p>Please correct the following problems:</p>\n"
    ...         '<ul class="form_errors"><li class="form_error">'
    ...         r'$(? "</li>\n<li class=\"form_error\">".join(errors) ?)'
    ...         '</li></ul>'
    ...     )

    >>> test(TestForm)
    HTTP/1.0 200 OK
    ...
    Content-Type: text/html
    ...
    ...What is your favorite animal ?...
    ...<input type="text" name="name" value="Joey"/>...
    ...

    >>> test(TestForm, form=dict(name="Me", email="blah"))
    HTTP/1.0 200 OK
    ...
     <p>Please correct the following problems:</p>
    <ul class="form_errors"><li class="form_error">Hey, you're not Joe!</li></ul>
    ...<input type="text" name="name" value="Me"/>...


@form_handler, .errors, .form_success, .form_failure, .parse_form(),
.form_data, .form_defaults, 


Database Access
===============

.db, .db_connect(), .cursor(), .query(), Row


Templates
=========

Text, HTML, Template, .fragment(), .page(), .method(), .http_method(),
escape(), .errors_found, .show_errors

EvalMap, EvalTemplate



