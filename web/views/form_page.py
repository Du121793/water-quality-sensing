from .layout import _html_escape, _render_layout


# 顯示表單頁面
def render_form_page(base_path, title, active_path, fields, message, reset_prompt=False):
    rows = []
    for field in fields:
        if field.get("type") == "section":
            rows.append(
                '<tr class="section"><th colspan="2">{}</th></tr>'.format(
                    _html_escape(field.get("label", ""))
                )
            )
            continue
        if field.get("type") == "html":
            rows.append(field.get("html", ""))
            continue
        if field.get("type") == "link":
            label = _html_escape(field.get("label", ""))
            href = _html_escape(field.get("href", ""))
            text = _html_escape(field.get("text", "下載"))
            rows.append(
                '<tr><th>{}</th><td><a class="btn secondary" href="{}">{}</a></td></tr>'.format(
                    label, href, text
                )
            )
            continue
        label = _html_escape(field.get("label", ""))
        name = _html_escape(field.get("name", ""))
        value = field.get("value", "")
        ftype = field.get("input", "text")
        placeholder = _html_escape(field.get("placeholder", ""))
        help_text = field.get("help")
        step_attr = ""
        if ftype == "number" and field.get("step"):
            step_attr = ' step="{}"'.format(_html_escape(field.get("step")))

        readonly_attr = " readonly" if field.get("readonly") else ""
        disabled_attr = " disabled" if field.get("disabled") else ""
        rows_attr = ""
        if ftype == "textarea":
            row_count = field.get("rows", 6)
            rows_attr = ' rows="{}"'.format(_html_escape(row_count))

        if ftype == "select":
            options = field.get("options", [])
            opt_html = []
            for opt_value, opt_label in options:
                selected = " selected" if str(value) == str(opt_value) else ""
                opt_html.append(
                    '<option value="{}"{}>{}</option>'.format(
                        _html_escape(opt_value),
                        selected,
                        _html_escape(opt_label),
                    )
                )
            input_html = '<select name="{}"{}{}>{}</select>'.format(
                name, readonly_attr, disabled_attr, "".join(opt_html)
            )
        elif ftype == "textarea":
            input_html = (
                '<textarea name="{}" placeholder="{}"{}{}{}>{}</textarea>'.format(
                    name,
                    placeholder,
                    rows_attr,
                    readonly_attr,
                    disabled_attr,
                    _html_escape(value, escape_quotes=False),
                )
            )
        else:
            input_html = (
                '<input type="{}" name="{}" value="{}" placeholder="{}"{}{}{} />'.format(
                    ftype,
                    name,
                    _html_escape(value, escape_quotes=True),
                    placeholder,
                    step_attr,
                    readonly_attr,
                    disabled_attr,
                )
            )
        if help_text:
            input_html += '<div class="muted">{}</div>'.format(
                _html_escape(help_text)
            )
        rows.append("<tr><th>{}</th><td>{}</td></tr>".format(label, input_html))

    prompt = ""
    if reset_prompt:
        prompt = """<div class="prompt">
  <span>設定已儲存，是否立即重啟？</span>
  <form method="post" action="{action}">
    <button class="btn" type="submit">立即重啟</button>
  </form>
  <form method="post" action="{dismiss}">
    <button class="btn secondary" type="submit">稍後</button>
  </form>
</div>""".format(
            action=base_path + "/reset",
            dismiss=base_path + "/reset-dismiss",
        )

    actions = """<div class="actions">
  <form method="post" action="{action}">
    <button class="btn secondary" type="submit">重啟裝置</button>
  </form>
</div>""".format(
        action=base_path + "/reset"
    )

    content = """{prompt}
{actions}
<form method="post" action="{action}">
  <table>
    {rows}
  </table>
  <button class="btn" type="submit">儲存</button>
</form>""".format(
        action=active_path, rows="".join(rows), prompt=prompt, actions=actions
    )
    return _render_layout(base_path, title, content, active_path, message)
