import http.server
import locale
import os
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Final

import cyclopts
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.text import Text

from hipertexto import __version__

from .jinja_globals import rel_path
from .process_md import process_markdown
from .styles import error, success, warning

console = Console()
e_console = Console(stderr=True)
app = cyclopts.App(
    name='ht',
    help='Use ht --help to see the available commands',
    version=__version__,
    console=console,
)

CURRENT_SCRIPT_PATH: Final[Path] = Path(__file__).resolve()
TEMPLATES_DIR: Final[Path] = CURRENT_SCRIPT_PATH.parent / 'templates'


def sort_by_key(page_metadata, key='title'):
    return page_metadata[key]


def validate_hipertexto_project():
    # searching for config.toml
    config_file = Path('.') / 'config.toml'

    if not config_file.exists():
        e_console.print('Not a hipertexto project', style='white on red')
        sys.exit(1)

    with config_file.open('rb') as f:
        config_toml = tomllib.load(f)

    # config file should have hipertexto table
    hipertexto_table = config_toml.get('hipertexto')

    if not hipertexto_table:
        e_console.print(
            'config.toml should have a hipertexto table', style=error
        )
        sys.exit(1)


@app.command()
def start(name: str):
    """Start a new project"""

    project_dir = Path(name)
    try:
        project_dir.mkdir()
    except FileExistsError as e:
        e_console.print(f'File {e.filename} already exists', style=error)
        sys.exit(1)

    (project_dir / 'content').mkdir()
    (project_dir / 'templates').mkdir()
    (project_dir / 'static').mkdir()
    (project_dir / 'styles').mkdir()

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template('config.toml.jinja2')
    config = template.render(name=name)
    with open(
        project_dir / 'config.toml',
        'w',
        encoding=locale.getpreferredencoding(False),
    ) as f:
        f.write(config)

    styled_name = Text(name, style=success)
    console.print(f'Project {styled_name.markup} created successfully')


@app.command()
def build():
    """Build your site to the public folder"""

    validate_hipertexto_project()

    root_path = Path('.')
    directories = {
        'root': root_path,
        'contents': root_path / 'content',
        'styles': root_path / 'styles',
        'static': root_path / 'static',
        'templates': root_path / 'templates',
        'public': Path('public'),
    }

    directories['public'].mkdir(exist_ok=True)

    # content and templates must exist and not be empty
    content_is_empty = not directories['contents'].exists() or not any(
        directories['contents'].iterdir()
    )
    template_is_empty = not directories['templates'].exists() or not any(
        directories['templates'].iterdir()
    )
    if content_is_empty or template_is_empty:
        e_console.print(
            'Content and Templates directories cannot be empty',
            style=error,
        )
        sys.exit(1)

    # Styles and Static content should be on public
    for dir_path in {
        directories['styles'],
        directories['static'],
    }:
        if not dir_path.is_dir():
            continue

        for item in dir_path.iterdir():
            dest_path = directories['public'] / item.name
            if item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_path)

    env = Environment(loader=FileSystemLoader(directories['templates']))
    env.globals['rel_path'] = rel_path

    try:
        for item in directories['contents'].iterdir():
            if item.is_dir():
                index_file = item / '_index.md'
                section_dir = directories['public'] / item.name
                section_dir.mkdir(parents=True, exist_ok=True)
                section_pages = []

                for file in item.glob('*.md'):
                    if file != index_file:
                        page_context = process_markdown(
                            file=file,
                            jinja_env=env,
                            content_dir=directories['contents'],
                            public_dir=directories['public'],
                            root_dir=directories['root'],
                            section_dir=section_dir,
                        )
                        section_pages.append(page_context)

                if index_file.exists():
                    section_pages.sort(key=sort_by_key, reverse=True)
                    process_markdown(
                        file=index_file,
                        jinja_env=env,
                        content_dir=directories['contents'],
                        public_dir=directories['public'],
                        root_dir=directories['root'],
                        section_dir=section_dir,
                        section_pages=section_pages,
                    )

            elif item.suffix == '.md':
                process_markdown(
                    file=item,
                    jinja_env=env,
                    content_dir=directories['contents'],
                    public_dir=directories['public'],
                    root_dir=directories['root'],
                )

        console.print('Site built successfully', style=success)

    except Exception as e:
        e_console.print(f'Error: {e}', style=error)
        sys.exit(1)


@app.command()
def serve(port: int = 8080):
    """Run a http server from public folder"""
    try:
        os.chdir('public')
    except FileNotFoundError:
        e_console.print('public folder not found', style=error)
        hipertexto_build = Text('ht build', style=success)
        e_console.print(
            f'Run {hipertexto_build.markup} before running "ht serve" again'
        )
        sys.exit(1)

    with http.server.HTTPServer(
        ('', port), http.server.SimpleHTTPRequestHandler
    ) as httpd:
        console.print(
            f'Serving at [link=http://127.0.0.1:{port}]http://127.0.0.1:{port}[/link]',
            style=success,
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.shutdown()
            console.print('\nLocal server stopped.', style=warning)
