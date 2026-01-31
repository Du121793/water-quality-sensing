from .layout import _render_layout


# 顯示更新前下載提示頁
def render_confirm_download_page(base_path, message, download_url):
    title = "更新確認"
    content = """<p class="muted">更新前建議先下載舊設定檔備份</p>
<div class="actions">
  <a class="btn secondary" href="{download_url}">下載舊設定檔</a>
</div>
<div class="actions">
  <form method="post" action="{confirm_action}">
    <button class="btn" type="submit">繼續儲存</button>
  </form>
  <form method="post" action="{cancel_action}">
    <button class="btn secondary" type="submit">取消</button>
  </form>
</div>""".format(
        download_url=download_url,
        confirm_action=base_path + "/confirm-save",
        cancel_action=base_path + "/confirm-cancel",
    )
    return _render_layout(base_path, title, content, "", message)
