"""Small self-contained HTML pages used during checkout redirects."""

import html
from typing import Dict


def _page(title: str, subtitle: str, body: str, script: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Vidhya</title>
<style>
  :root {{ --brand:#4680FF; --ink:#1d2634; --muted:#6b7280; --line:#e5e9f0; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         background:#f4f6fb; color:var(--ink); font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif; }}
  .card {{ width:min(440px,92vw); background:#fff; border:1px solid var(--line); border-radius:16px;
           padding:28px; box-shadow:0 18px 50px rgba(30,42,64,.08); }}
  .brand {{ display:flex; align-items:center; gap:10px; margin-bottom:18px; }}
  .dot {{ width:34px; height:34px; border-radius:10px; background:var(--brand); color:#fff;
          display:flex; align-items:center; justify-content:center; font-weight:800; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  p {{ margin:0; color:var(--muted); font-size:13px; line-height:1.55; }}
  .amount {{ margin:20px 0; padding:16px; border-radius:12px; background:#f6f8fd; border:1px solid var(--line); }}
  .amount b {{ display:block; font-size:24px; margin-top:2px; }}
  .row {{ display:flex; gap:10px; margin-top:18px; }}
  button, .btn {{ flex:1; border:0; border-radius:10px; padding:12px 14px; font-size:14px; font-weight:600;
                  cursor:pointer; text-decoration:none; text-align:center; display:inline-block; }}
  .primary {{ background:var(--brand); color:#fff; }}
  .ghost {{ background:#fff; color:var(--ink); border:1px solid var(--line); }}
  .danger {{ background:#fff1f2; color:#be123c; border:1px solid #fecdd3; }}
  .note {{ margin-top:16px; font-size:12px; color:var(--muted); }}
  .spin {{ width:28px; height:28px; border:3px solid #dbe4ff; border-top-color:var(--brand);
           border-radius:50%; animation:spin 1s linear infinite; margin:0 auto 12px; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
</style>
</head>
<body>
  <main class="card">
    <div class="brand"><span class="dot">V</span><strong>Vidhya</strong></div>
    <h1>{html.escape(title)}</h1>
    <p>{html.escape(subtitle)}</p>
    {body}
  </main>
  {f'<script>{script}</script>' if script else ''}
</body>
</html>"""


def _amount(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def demo_checkout_page(
    order_ref: str, plan_name: str, amount_paise: int, mode_note: str
) -> str:
    body = f"""
    <div class="amount"><span style="font-size:12px;color:#6b7280">Demo checkout · no real money</span>
      <b>{_amount(amount_paise)}</b><span style="font-size:12px;color:#6b7280">{html.escape(plan_name)}</span></div>
    <div class="row">
      <button class="primary" onclick="complete('success')">Simulate success</button>
      <button class="danger" onclick="complete('failed')">Simulate failure</button>
    </div>
    <p class="note">{html.escape(mode_note)}</p>
    """
    script = f"""
    function cookie(name) {{
      return document.cookie.split('; ').find(r => r.startsWith(name + '='))?.split('=')[1] || '';
    }}
    async function complete(result) {{
      const res = await fetch('/api/v1/payments/demo/{html.escape(order_ref)}/complete', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json', 'X-CSRF-Token': cookie('csrf_token') }},
        body: JSON.stringify({{ result }})
      }});
      if (res.status === 401) {{ location.href = '/login?next=' + encodeURIComponent(location.pathname); return; }}
      location.href = '/payment/status?txn_id={html.escape(order_ref)}';
    }}
    """
    return _page("Demo checkout", "This order is simulated locally. No gateway is called.", body, script)


def auto_post_page(
    title: str,
    subtitle: str,
    action_url: str,
    fields: Dict[str, str],
) -> str:
    inputs = "".join(
        f'<input type="hidden" name="{html.escape(str(k))}" value="{html.escape(str(v))}">'
        for k, v in fields.items()
    )
    body = f"""
    <div class="spin"></div>
    <p>Redirecting to the payment gateway…</p>
    <form id="pg" method="post" action="{html.escape(action_url)}">{inputs}
      <div class="row"><button class="primary" type="submit">Continue to payment</button></div>
    </form>
    <p class="note">If nothing happens, tap “Continue to payment”.</p>
    """
    script = "setTimeout(() => document.getElementById('pg').submit(), 350);"
    return _page(title, subtitle, body, script)


def cashfree_checkout_page(
    title: str, subtitle: str, session_id: str, mode: str
) -> str:
    body = """
    <div class="spin"></div>
    <p>Opening Cashfree checkout…</p>
    <div class="row"><button class="primary" onclick="openCheckout()">Continue to payment</button></div>
    <p class="note">If the checkout does not open, tap the button above.</p>
    """
    script = f"""
    const cashfree = Cashfree({{ mode: "{'sandbox' if mode != 'production' else 'production'}" }});
    function openCheckout() {{
      cashfree.checkout({{ paymentSessionId: "{html.escape(session_id)}", redirectTarget: "_self" }});
    }}
    setTimeout(openCheckout, 500);
    """
    return _page(title, subtitle, body, script).replace(
        "</head>",
        '<script src="https://sdk.cashfree.com/js/v3/cashfree.js"></script>\n</head>',
    )
