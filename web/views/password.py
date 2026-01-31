from .layout import _render_layout


# 顯示修改密碼頁面
def render_password_page(base_path, message):
    title = "修改管理密碼"
    content = """<form method="post" action="{base}/password">
  <p class="muted">修改後需要重新登入</p>
  <table>
    <tr><th>當前密碼</th><td><input type="password" name="current_password" /></td></tr>
    <tr><th>新密碼</th><td><input type="password" name="new_password" /></td></tr>
    <tr><th>再次輸入</th><td><input type="password" name="new_password2" /></td></tr>
  </table>
  <button class="btn" type="submit">更新密碼</button>
</form>""".format(
        base=base_path
    )
    return _render_layout(
        base_path, title, content, base_path + "/password", message
    )
