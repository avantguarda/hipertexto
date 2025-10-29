from typing import Literal

from jinja2 import pass_context
from jinja2.runtime import Context


@pass_context
def rel_path(
    context: Context,
    file_path: str,
    resource_type: Literal['static', 'style'],
) -> str:
    if resource_type not in {'static', 'style'}:
        raise ValueError('resource_type must be either static or style')

    levels_to_go_up = context['page']['depth']

    relative_path_to_root = '../' * levels_to_go_up

    return f'{relative_path_to_root}{file_path}'
