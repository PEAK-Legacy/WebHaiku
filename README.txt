


    >>> from web_haiku import Page, test, HTML
    >>> class HelloPage(Page):
    ...     body = HTML("<h1>Hello, world!</h1>")

    >>> test(HelloPage)
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    ...
    <h1>Hello, world!</h1>


    >>> test(HelloPage, PATH_INFO="/x")
    HTTP/1.0 404 Not Found
    Date: ...
    Content-Type: text/plain
    ...
    404 not found
    You deserve a kinder note
    Than this web haiku!
    ...

    >>> test(HelloPage, form={"a":"b"})
    HTTP/1.0 405 Method not allowed
    Date: ...
    Content-Type: text/plain
    Allow: HEAD, GET
    ...
    Excellent method!
    Alas, my response must be:
    "I cannot comply."

    >>> test(HelloPage, REQUEST_METHOD="HEAD")
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    Content-Length: 22
    <BLANKLINE>
    <BLANKLINE>

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

    >>> class Folder(Page):
    ...     hello = HelloPage
    ...     form = TestForm

    >>> test(Folder, PATH_INFO="/hello")
    HTTP/1.0 200 OK
    Date: ...
    Content-Type: text/html
    ...
    <h1>Hello, world!</h1>

    >>> test(Folder, PATH_INFO="/hello/")
    HTTP/1.0 302 Found
    Date: ...
    Content-Type: text/html
    Location: http://127.0.0.1/hello
    ...
    ...<meta http-equiv="refresh" content="0;url=http://127.0.0.1/hello" />...

    >>> test(Folder, PATH_INFO="/form")
    HTTP/1.0 200 OK
    ...
    Content-Type: text/html
    ...
    ...What is your favorite animal ?...
    ...<input type="text" name="name" value="Joey"/>...
    ...

    >>> test(Folder, form=dict(name="Me", email="blah"), PATH_INFO="/form")
    HTTP/1.0 200 OK
    ...
     <p>Please correct the following problems:</p>
    <ul class="form_errors"><li class="form_error">Hey, you're not Joe!</li></ul>
    ...<input type="text" name="name" value="Me"/>...

