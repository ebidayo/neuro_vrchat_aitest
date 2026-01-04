from main import format_url_for_display

def test_format_url_for_display_short():
    url = "https://example.com/abc"
    assert format_url_for_display(url) == url

def test_format_url_for_display_long():
    url = "https://verylongdomain.example.com/this/is/a/very/long/path/that/should/be/shortened"
    display = format_url_for_display(url, max_len=32)
    assert display.startswith("verylongdomain.example.com/")
    assert display.endswith("…")

def test_format_url_for_display_invalid():
    url = "not a url at all"
    display = format_url_for_display(url, max_len=10)
    assert display.endswith("…") or display == url[:9] + "…"

def test_format_url_for_display_empty():
    assert format_url_for_display("") == ""
    assert format_url_for_display(None) == ""
