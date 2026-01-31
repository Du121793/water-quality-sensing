from .layout import _render_layout


# 顯示登入/設定密碼頁面
def render_login_page(base_path, message, is_init):
    if is_init:
        title = "初始化管理密碼"
        content = """<form method="post" action="{base}/login">
  <p class="muted">第一次使用請設定管理密碼</p>
  <table>
    <tr><th>新密碼</th><td><input type="password" name="password" /></td></tr>
    <tr><th>再次輸入</th><td><input type="password" name="password2" /></td></tr>
  </table>
  <button class="btn" type="submit">設定密碼</button>
</form>""".format(
            base=base_path
        )
    else:
        title = "管理員登入"
        content = """<form method="post" action="{base}/login">
  <p class="muted">請輸入管理密碼</p>
  <table>
    <tr><th>密碼</th><td><input type="password" name="password" /></td></tr>
  </table>
  <button class="btn" type="submit">登入</button>
</form>""".format(
            base=base_path
        )
    return _render_layout(base_path, title, content, "", message, show_nav=False)
