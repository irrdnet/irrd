import wtforms
import wtforms_bootstrap5
from markupsafe import Markup
from starlette.responses import Response

from irrd.conf import get_setting
from irrd.webui import templates
from irrd.webui.helpers import get_messages


def template_context_render(template_name, request, context) -> Response:
    """
    Render a template with context to a Response.
    Adds a few items to the context, then returns a TemplateResponse.
    """
    context["request"] = request
    context["messages"] = get_messages(request)
    context["readonly_standby"] = get_setting("readonly_standby")
    context["irrd_internal_migration_enabled"] = get_setting("auth.irrd_internal_migration_enabled")

    context["auth_sources"] = [
        name for name, settings in get_setting("sources", {}).items() if settings.get("authoritative")
    ]

    if "user" not in context:
        context["user"] = request.auth.user if request.auth.is_authenticated else None

    return templates.TemplateResponse(template_name, context)


def render_form(form: wtforms.Form) -> Markup:
    """
    Render the form in a nice horizontal format.
    """
    # the defaults for checkboxes and submits are weird and the API limited,
    # hence this hacky fix
    checkboxes = [field.name for field in form if isinstance(field.widget, wtforms.widgets.CheckboxInput)]
    submits = [field.name for field in form if isinstance(field.widget, wtforms.widgets.SubmitInput)]
    return (
        wtforms_bootstrap5.RendererContext()
        .form()
        .default_field(
            row_class="row mb-3",
            label_class="form-label col-sm-3 col-form-label",
            field_wrapper_class="col-sm-9",
            field_wrapper_enabled=True,
        )
        .field(
            *checkboxes,
            wrapper_class="offset-sm-3 col-sm-9",
            wrapper_enabled=True,
            field_wrapper_enabled=False,
        )
        .field(
            *submits,
            field_wrapper_class="offset-sm-3 col-sm-9",
            field_wrapper_enabled=True,
        )
    ).render(form)
