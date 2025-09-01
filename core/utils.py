from django.shortcuts import render


def hx_render(request, full_template: str, partial_template: str, context=None, status: int = 200):
    """
    Render a full page or a partial based on HX-Request header.
    - If HX-Request is present, render the partial_template without base layout.
    - Otherwise, render the full_template (which typically extends base.html).
    """
    context = context or {}
    if request.headers.get("HX-Request"):
        return render(request, partial_template, context, status=status)
    return render(request, full_template, context, status=status)