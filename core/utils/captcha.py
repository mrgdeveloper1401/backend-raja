from pypasser.captcha import arcaptcha

# Pure HTTP solve without opening a browser
result = arcaptcha.solve(
    site_key="t8xr2hpxue",
    domain="www.raja.ir",
)

if result.is_solved:
    print("arcaptcha-token:", result.response_token)