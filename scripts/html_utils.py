import os

def elem(
    tag_name: str,
    *content: str,
    **attributes: str,
) -> str:
    """Create an HTML element.
    
    Args:
        tag_name (str): the type of tag
        *content (str): the content of the tag
        **attributes (str): the tag's attributes
    
        When passing python reserved keywords as args: just use
        the dict spread syntax (idk the correct term)
        ```python
        elem('h1', 'hello', 
            **{
                'class': 'large'
            }
        )
        ```
    
    Returns:
        str: the tag in the following format:
        ```html
        <tag_name attributes,>content,</tag_name>
        ```
    """

    full_content = ' '.join(content)

    attrs = ' '.join([ 
        f'{key}="{value}"' 
        for key, value in attributes.items()
        if value is not None
    ])

    if attrs:
        head = f'{tag_name} {attrs}'
    else:
        head = tag_name

    return f'<{head}>{full_content}</{tag_name}>'

def table_row(
    *td: str,
    **attributes: str,
) -> str:
    """Create a tr element, wrapped as a function for ease

    Args:
        *td (str): the td elements, ideally it has to be created with `elem()` first
        **attributes (str): the `tr` attributes

    Returns:
        str: the `tr` element
    """
    
    return elem('tr', *td, **attributes)

def create_page_from_template(
    template_path: str,
    output_path: str,
    **variables: str,
) -> str | None:
    """Create a page from a template with the supplied variables.

    Args:
        template_path (str): A project root relative path to the template
        output_path (str): The output file, path also relative to the project root
        **variables (str): Variables to be supplied to the template.
        
        Templates should have `{{__name__}}` on them, `name` is the variable.
        
        index.template.html:
        ```html
        <html>
            <body>
            {{__content__}}
            </body>
        </html>
        ```
        Function call:
        ```python
        create_page_from_template(
            'index.template.html',
            'index.html',
            content='Hello!',
        )
        ```
    Returns:
        str | None: the output path if the operation succeeds, None if otherwise
    """
    
    current_dir = os.path.dirname(__file__)
    template_path = os.path.join(current_dir, '../' + template_path)

    try:
        with open(template_path) as file:
            html_template = file.read()
    except OSError:
        print('Supplied template does not exist.')
        return None
    except:
        print('Unexpected error occured')
        return None

    for var in variables:
        html_template = html_template.replace(
            '{{__' + var + '__}}',
            str(variables[var])
        )

    full_output_path = os.path.join(current_dir, '../', output_path)
    os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
    with open(output_path, 'w') as file:
        file.write(html_template)

    print('Created html file at: ' + full_output_path)
    return full_output_path

if __name__ == '__main__':
    h1_expect = '<h1 id="hhhhh" dumb-attribute="some value">meow quack</h1>'
    h1_actual = elem('h1', 'meow', 'quack', id='hhhhh', **{
        'dumb-attribute': 'some value'
    })
    assert h1_expect == h1_actual, f'Output mismatch:\n{h1_expect}\n{h1_actual}'

    tr_expect = '<tr data-gggg="quack">owo uwu nyaa</tr>'
    tr_actual = table_row('owo', 'uwu', 'nyaa', **{'data-gggg': 'quack'})
    assert tr_expect == tr_actual, f'Output mismatch:\n{tr_expect}\n{tr_actual}'

    create_page_from_template(
        'docs/main-page.template.html',
        'tests/test.test.html',
        updated_at='now'
    )